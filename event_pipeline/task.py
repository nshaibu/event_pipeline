import logging
import time
import typing
from functools import lru_cache
from collections import deque
from threading import Condition
from concurrent.futures import Executor, wait, Future
from enum import Enum, unique
from .base import EventBase
from . import parser
from .constants import EMPTY, EventResult
from .utils import generate_unique_id
from .exceptions import (
    PipelineError,
    BadPipelineError,
    ImproperlyConfigured,
    StopProcessingError,
    EventDoesNotExist,
)
from .utils import (
    build_event_arguments_from_pipeline,
    get_function_call_args,
    AcquireReleaseLock,
)

logger = logging.getLogger(__name__)


class ExecutionState(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    CANCELLED = "cancelled"
    FINISHED = "finished"
    ABORTED = "aborted"


class EventExecutionContext(object):
    """
    Represents the execution context for a particular event in the pipeline.

    This class encapsulates the necessary data and state associated with
    executing an event, such as the task being processed and the pipeline
    it belongs to.

    Individual events executing concurrently must acquire the "conditional_variable"
    before they can make any changes to the execution context. This ensures that only one
    event can modify the context at a time, preventing race conditions and ensuring thread safety.

    Attributes:
        task: The specific PipelineTask that is being executed.
        pipeline: The Pipeline that orchestrates the execution of the task.
    """

    def __init__(
        self,
        task: typing.Union["PipelineTask", typing.List["PipelineTask"]],
        pipeline: "Pipeline",
    ):
        generate_unique_id(self)
        self.conditional_variable = Condition()

        self._execution_start_tp: float = time.time()
        self._execution_end_tp: float = 0
        self.task_profiles = task if isinstance(task, (tuple, list)) else [task]
        self.pipeline = pipeline
        self.execution_result: typing.List[EventResult] = []
        self.state: ExecutionState = ExecutionState.PENDING

        self.previous_context: typing.Optional[EventExecutionContext] = None

        self._errors: typing.List[PipelineError] = []

    @property
    def id(self):
        return generate_unique_id(self)

    def _gather_executors_for_parallel_executions(
        self,
    ) -> typing.Dict[typing.Type[Executor], typing.Dict[str, typing.Any]]:
        """
        Gathers and returns the executors required for parallel executions, along with their associated configurations.

        This method is responsible for identifying the executors that will be used to execute tasks in parallel
        and collects their respective configuration settings. The result is a dictionary where each key is a
        type of executor (e.g., `Executor` type), and each value is a dictionary containing the specific parameters
        or settings for that executor.

        Returns:
            dict: A dictionary where:
                - The key is the type of the executor (Executor class/type).
                - The value is a dictionary containing configuration data or parameters required by that executor
                  for parallel execution.

        Example:
            executors = self._gather_executors_for_parallel_executions()
            for executor_type, config in executors.items():
                # Use the executor_type and its config to perform parallel execution
        """
        executors_map = {}

        for task in self.task_profiles:
            event, context, event_call_args = self._get_executor_context_and_event(task)
            executor = event.get_executor_class()

            if executor in executors_map:
                executors_map[executor][event] = {
                    "event": event,
                    "call_args": event_call_args,
                }
                previous_context = executors_map[executor]["context"]
                if previous_context:
                    executors_map[executor]["context"] = previous_context
                else:
                    for key, value in context.items():
                        if previous_context.get(key, 0) == value:
                            continue
                        elif isinstance(value, EMPTY):
                            continue
                        elif str(value).isnumeric():
                            previous_value = previous_context.get(key, 0)
                            if str(previous_value).isnumeric():
                                executors_map[executor]["context"][key] = max(
                                    [int(value), int(previous_value)]
                                )
            else:
                executors_map[executor] = {
                    "context": context,
                    event: {
                        "event": event,
                        "call_args": event_call_args,
                    },
                }

        return executors_map

    def __getstate__(self):
        state = self.__dict__.copy()
        if self.previous_context:
            state["previous_context"] = {
                "_id": self.previous_context.id,
                "execution_result": self.previous_context.execution_result,
                "_execution_start_tp": self.previous_context._execution_start_tp,
                "_execution_end_tp": self.previous_context._execution_end_tp,
                "state": self.previous_context.state,
                "_errors": self._errors,
            }
        else:
            state["previous_context"] = None
        return state

    def __setstate__(self, state):
        previous = state.pop("previous_context", None)
        if previous:
            instance = self.__class__(
                task=state["task_profiles"], pipeline=state["pipeline"]
            )
            instance.__dict__.update(previous)
            state["previous_context"] = instance
        else:
            state["previous_context"] = None
        self.__dict__.update(state)

    def __hash__(self):
        return hash(self.id)

    def execution_failed(self):
        with self.conditional_variable:
            if self.state in [ExecutionState.CANCELLED, ExecutionState.ABORTED]:
                return True
            return len(self.execution_result) == 0 and self._errors

    def execution_success(self):
        with self.conditional_variable:
            if self.state in [ExecutionState.CANCELLED, ExecutionState.ABORTED]:
                return False
            return self.execution_result

    def init_and_execute_events(self) -> typing.List[Future]:
        """
        Initializes and executes events in parallel, returning a list of Future objects representing the execution
         progress.

        This method first gathers the executors required for parallel execution using the
        `_gather_executors_for_parallel_executions` method.
        It then initializes the execution of events across multiple executors. The method returns a list of `Future`
        objects which allow tracking the status of each parallel execution.

        The `Future` objects can be used to monitor or retrieve the results of each event execution once completed.

        Returns:
            List[Future]: A list of `Future` objects, each representing an ongoing or completed event execution.

        Example:
            futures = self.init_and_execute_events()
            for future in futures:
                result = future.result()  # Wait for and get the result of the event execution
        """

        futures = []

        executor_maps = self._gather_executors_for_parallel_executions()

        for executor_klass, execution_config in executor_maps.items():

            executor_klass_config: typing.Dict[str, typing.Any] = execution_config.pop(
                "context", {}
            )

            if len(execution_config) == 1:
                event_config = list(execution_config.values())[0]

                with executor_klass(**executor_klass_config) as executor:
                    future = executor.submit(
                        event_config["event"], **event_config["call_args"]
                    )
                    futures.append(future)
            else:
                # parallel execution with common executor
                with executor_klass(**executor_klass_config) as executor:
                    future = [
                        executor.submit(
                            event_config["event"], **event_config["call_args"]
                        )
                        for _, event_config in execution_config.items()
                    ]
                    futures.extend(future)

        return futures

    def _get_executor_context_and_event(
        self, task_profile: "PipelineTask"
    ) -> typing.Tuple[
        EventBase, typing.Dict[str, typing.Any], typing.Dict[str, typing.Any]
    ]:
        """
        Retrieves the executor context and associated event information for a given pipeline task.

        Args:
            task_profile (PipelineTask): The task profile containing the necessary information
                                         for context and event extraction.

        Returns:
            Tuple[EventBase, dict, dict]:
                - The first element is an EventBase object representing the event related
                  to the task execution.
                - The second element is a dictionary containing context-specific data
                  required by the executor.
                - The third element is a dictionary that holds additional metadata or
                  configuration settings relevant to the event.
        """

        event_klass = task_profile.get_event_klass()
        if not issubclass(event_klass.get_executor_class(), Executor):
            raise ImproperlyConfigured(f"Event executor must inherit {Executor}")

        logger.info(f"Executing event '{task_profile.event}'")

        event_init_arguments, event_call_arguments = (
            build_event_arguments_from_pipeline(event_klass, self.pipeline)
        )

        event_init_arguments = event_init_arguments or {}
        event_call_arguments = event_call_arguments or {}

        event_init_arguments["execution_context"] = self
        event_init_arguments["task_id"] = task_profile.id

        pointer_type = task_profile.get_pointer_type_to_this_event()
        if pointer_type == PipeType.PIPE_POINTER:
            if self.previous_context:
                event_init_arguments["previous_event_result"] = (
                    self.previous_context.execution_result
                )
            else:
                event_init_arguments["previous_event_result"] = EMPTY

        event = event_klass(**event_init_arguments)
        executor_klass = event.get_executor_class()

        context = event.get_executor_context()
        context = get_function_call_args(executor_klass.__init__, context)

        return event, context, event_call_arguments

    def dispatch(self):
        """
        Dispatches an action or event to the appropriate handler or process.

        This method is responsible for routing the event or action to the correct
        handler based on the context, ensuring that the proper logic is executed
        for the given task or event.

        """

        try:
            self.state = ExecutionState.EXECUTING

            futures = self.init_and_execute_events()
            waited_results = wait(futures)

            self.process_executor_results(waited_results)

            self.state = ExecutionState.FINISHED
        except Exception as e:
            logger.exception(str(e), exc_info=e)
            self.state = ExecutionState.ABORTED
            task_error = BadPipelineError(
                message={"status": 0, "message": str(e)},
                exception=e,
            )
            self._errors.append(task_error)

        try:
            self.conditional_variable.notify_all()
        except RuntimeError:
            pass

        self._execution_end_tp = time.time()

        logger.info(
            f"Finished executing task(s) '{self.task_profiles}' with status {self.state}"
        )

    def process_executor_results(self, waited_results):
        """
        Processes the results from the executor after events has been executed, handling any awaited results.

        Args:
            waited_results (Any): The results that were awaited during execution, which need to be processed.

        Returns:
            None: This method modifies internal states of the execution context and performs actions based on
             the event and results, without returning a value.

        Side Effects:
            This method may update internal attributes or trigger additional operations based on the results
            from the event and waited results.
        """
        with AcquireReleaseLock(self.conditional_variable):

            for fut in waited_results.done:
                try:
                    result = fut.result()
                except Exception as e:
                    params = getattr(e, "params", {})
                    event_name = params.get("event", "Unknown")

                    logger.exception(f"{event_name}: {str(e)}")

                    if isinstance(e, StopProcessingError):
                        self.state = ExecutionState.CANCELLED

                    result = EventResult(
                        is_error=True,
                        detail=str(e),
                        task_id=params.get("task_id"),
                        event_name=event_name,
                        init_params=params.get("init_args"),
                        call_params=params.get("call_args"),
                    )

                if result.is_error:
                    self._errors.append(
                        PipelineError(
                            message=result.detail,
                            code=result.task_id,
                            params=result._asdict(),
                        )
                    )
                else:
                    self.execution_result.append(result)


@unique
class PipeType(Enum):
    POINTER = "pointer"
    PIPE_POINTER = "pipe_pointer"
    PARALLELISM = "parallelism"

    def token(self):
        if self == self.POINTER:
            return "->"
        elif self == self.PIPE_POINTER:
            return "|->"
        elif self == self.PARALLELISM:
            return "||"


class PipelineTask(object):
    """
    Represents a task in a pipeline, with event-driven behavior and conditional execution flows.

    Each `PipelineTask` is part of a tree structure, where tasks can have dependent tasks that execute
    on success or failure. These dependencies are defined through `on_success_event`, `on_failure_event`,
    and associated pipes. The task tree is built based on the instructions provided in the pointy script.

    Attributes:
        event (typing.Type[EventBase] | str): The event type or event name that triggers the task execution.
        on_success_event (typing.Optional["PipelineTask"]): A task to execute if this task is successful.
        on_failure_event (typing.Optional["PipelineTask"]): A task to execute if this task fails.
        on_success_pipe (typing.Optional[PipeType]): A pipe to use if the task is successful.
        on_failure_pipe (typing.Optional[PipeType]): A pipe to use if the task fails.
    """

    def __init__(
        self,
        event: typing.Union[typing.Type[EventBase], str],
        on_success_event: typing.Optional["PipelineTask"] = None,
        on_failure_event: typing.Optional["PipelineTask"] = None,
        on_success_pipe: typing.Optional[PipeType] = None,
        on_failure_pipe: typing.Optional[PipeType] = None,
    ):
        generate_unique_id(self)

        # attributes for when a task is created from a descriptor
        self._descriptor: typing.Optional[int] = None
        self._descriptor_pipe: typing.Optional[PipeType] = None

        self.event = event
        self.parent_node: typing.Optional[PipelineTask] = None

        # sink event this is where the conditional events collapse
        # into after they are done executing
        self.sink_node: typing.Optional[PipelineTask] = None
        self.sink_pipe: typing.Optional[PipeType] = None

        # conditional events
        self.on_success_event = on_success_event
        self.on_failure_event = on_failure_event
        self.on_success_pipe = on_success_pipe
        self.on_failure_pipe = on_failure_pipe

    @property
    def id(self) -> str:
        return generate_unique_id(self)

    def __str__(self):
        return self.event

    def __repr__(self):
        return f"{self.event} -> [{repr(self.on_success_event)}, {repr(self.on_failure_event)}]"

    def __hash__(self):
        return hash(self.id)

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("on_failure_event", None)
        state.pop("on_success_event", None)
        state.pop("sink_node", None)
        state.pop("parent_node", None)
        for field in ["sink_node", "on_failure_event", "on_success_event"]:
            node = getattr(self, field, None)
            if node:
                state[field] = {
                    "event": node.event,
                    "_id": node.id,
                    "_descriptor": node._descriptor,
                    "_descriptor_pipe": node._descriptor_pipe,
                }
        return state

    def __setstate__(self, state):
        for field in ["sink_node", "on_failure_event", "on_success_event"]:
            if field in state and state[field] is not None:
                _state = state[field]
                state[field] = self.__class__(event=_state["event"])
                state[field]._id = _state["_id"]

        self.__dict__.update(state)

    @property
    def is_conditional(self):
        return self.on_success_event and self.on_failure_event

    @property
    def is_descriptor_task(self):
        """
        Determines if the current task is a descriptor node.

        A descriptor node is a conditional node that is executed based on the result
        of its parent node's execution. In the pointy language, a value of 0 represents
        a failure descriptor, and a value of 1 represents a success descriptor.

        Returns:
            bool: True if the task is a descriptor node, False otherwise.
        """
        return self._descriptor is not None or self._descriptor_pipe is not None

    @property
    def is_sink(self) -> bool:
        """
        Determines if the current PipelineTask is a sink node.

        A sink node is executed after all the child nodes of its parent have
        finished executing. This method checks if the current task is classified
        as a sink node in the pipeline.

        Returns:
            bool: True if the task is a sink node, False otherwise.
        """
        parent = self.parent_node
        if parent and not self.is_descriptor_task:
            return parent.sink_node == self
        return False

    def get_event_klass(self):
        return self.resolve_event_name(self.event)

    @classmethod
    @lru_cache()
    def resolve_event_name(
        cls, event_name: typing.Union[str, typing.Type[EventBase]]
    ) -> typing.Type[EventBase]:
        """Resolve event class"""
        if not isinstance(event_name, str):
            return event_name

        for event in cls.get_event_klasses():
            klass_name = event.__name__.lower()
            if klass_name == event_name.lower():
                return event
        raise EventDoesNotExist(f"'{event_name}' was not found.")

    @staticmethod
    def get_event_klasses():
        yield from EventBase.get_event_klasses()

    @classmethod
    def build_pipeline_from_execution_code(cls, code: str):
        """
        Constructs a pipeline based on the provided execution code.

        This method parses and processes the given execution code to build a corresponding pipeline
        that can be executed within the system.

        Args:
            code (str): The execution code as a string, typically representing a sequence of
                        operations or instructions to construct the pipeline.

        Returns:
            Pipeline: The constructed pipeline based on the provided execution code.

        Raises:
            SyntaxError: If the execution code is invalid or cannot be parsed to form a pipeline.
            Index: If not code provided.

        Example:
            pipeline = PipelineTask.build_pipeline_from_execution_code("A->B->V")
        """
        if not code:
            raise IndexError("No pointy code provided")

        ast = parser.pointy_parser(code)
        tail = cls._parse_ast(ast)
        return tail.get_root()

    @classmethod
    def _parse_ast(cls, ast):
        """
        Parses the provided abstract syntax tree (AST) to extract relevant information.

        Args:
            ast: The abstract syntax tree (AST) to be parsed, typically representing
                 structured data or code for further processing.

        Returns:
            The parsed result, which may vary depending on the AST structure and
            the implementation of the parsing logic.

        TODO:
            - Add detailed explanation of the algorithm and its steps.
        """
        if isinstance(ast, parser.BinOp):
            left_node = cls._parse_ast(ast.left)
            right_node = cls._parse_ast(ast.right)

            if isinstance(left_node, PipelineTask) and isinstance(
                right_node, PipelineTask
            ):
                if ast.op == PipeType.PIPE_POINTER.token():
                    pipe_type = PipeType.PIPE_POINTER
                elif ast.op == PipeType.POINTER.token():
                    pipe_type = PipeType.POINTER
                else:
                    pipe_type = PipeType.PARALLELISM

                if left_node.is_conditional:
                    left_node.sink_node = right_node
                    left_node.sink_pipe = pipe_type
                else:
                    left_node.on_success_event = right_node
                    left_node.on_success_pipe = pipe_type

                right_node.parent_node = left_node
                return right_node
            elif isinstance(left_node, int) or isinstance(right_node, int):
                descriptor_value = node = None
                if isinstance(left_node, int):
                    descriptor_value = left_node
                else:
                    node = left_node

                if isinstance(right_node, int):
                    descriptor_value = right_node
                else:
                    node = right_node

                if node:
                    node = node.get_root()
                    node._descriptor = descriptor_value
                    node._descriptor_pipe = ast.op
                    return node
                # TODO : Better error message
                raise SyntaxError(f"AST is malformed {ast}")
            else:
                return left_node or right_node
        elif isinstance(ast, parser.TaskName):
            return cls(event=ast.value)
        elif isinstance(ast, parser.ConditionalBinOP):
            left_node = cls._parse_ast(ast.left)
            right_node = cls._parse_ast(ast.right)

            if left_node:
                left_node = left_node.get_root()

            if right_node:
                right_node = right_node.get_root()

            parent = cls(event=ast.parent.value)

            for node in [right_node, left_node]:
                if node:
                    node.parent_node = parent
                    if node._descriptor == 0:
                        parent.on_failure_event = node
                        parent.on_failure_pipe = (
                            PipeType.POINTER
                            if node._descriptor_pipe == PipeType.POINTER.token()
                            else PipeType.PIPE_POINTER
                        )
                    else:
                        parent.on_success_event = node
                        parent.on_success_pipe = (
                            PipeType.POINTER
                            if node._descriptor_pipe == PipeType.POINTER.token()
                            else PipeType.PIPE_POINTER
                        )

            return parent
        elif isinstance(ast, parser.Descriptor):
            return int(ast.value)

    def get_children(self):
        children = []
        if self.on_failure_event:
            children.append(self.on_failure_event)
        if self.sink_node:
            children.append(self.sink_node)
        if self.on_success_event:
            children.append(self.on_success_event)
        return children

    def get_root(self):
        if self.parent_node is None:
            return self
        return self.parent_node.get_root()

    def get_task_count(self) -> int:
        root = self.get_root()
        nodes = yield from self.bf_traversal(root)
        return len(nodes)

    @classmethod
    def bf_traversal(cls, node: "PipelineTask"):
        if node:
            yield node

            for child in node.get_children():
                yield from cls.bf_traversal(child)

    def get_pointer_type_to_this_event(self) -> PipeType:
        pipe_type = PipeType.POINTER
        if self.parent_node is not None:
            if (
                self.parent_node.on_success_event
                and self.parent_node.on_success_event == self
            ):
                pipe_type = self.parent_node.on_success_pipe
            elif (
                self.parent_node.on_failure_event
                and self.parent_node.on_failure_event == self
            ):
                pipe_type = self.parent_node.on_failure_pipe
            elif self.parent_node.sink_node and self.parent_node.sink_node == self:
                pipe_type = self.parent_node.sink_pipe

        return pipe_type

    @classmethod
    def execute_task(
        cls,
        task: "PipelineTask",
        pipeline: "Pipeline",
        sink_queue: deque,
        previous_context: typing.Optional[EventExecutionContext] = None,
    ):
        """
        Executes a specific task in the pipeline and manages the flow of data.

        Args:
            cls: The class that the method is bound to.
            task: The pipeline task to be executed.
            pipeline: The pipeline object that orchestrates the task execution.
            sink_queue: The queue used to store sink nodes for later processing.
            previous_context: An optional EventExecutionContext containing previous
                              execution context, if available.

        This method performs the necessary operations for executing a task, handles
        task-specific logic, and updates the sink queue with sink nodes for further processing.
        """
        if task:
            if previous_context is None:
                execution_context = EventExecutionContext(pipeline=pipeline, task=task)
                pipeline.execution_context = execution_context
            else:
                if task.sink_node:
                    sink_queue.append(task.sink_node)

                parallel_tasks = set()

                # Loop through the chain of tasks, adding each task to the 'parallel_tasks' set,
                # until we encounter a task where the 'on_success_pipe' is no longer equal
                # to PipeType.PARALLELISM.
                # This indicates that the task is part of a parallel execution chain.
                while task and task.on_success_pipe == PipeType.PARALLELISM:
                    parallel_tasks.add(task)
                    task = task.on_success_event

                if parallel_tasks:
                    parallel_tasks.add(task)

                execution_context = EventExecutionContext(
                    pipeline=pipeline,
                    task=list(parallel_tasks) if parallel_tasks else task,
                )

                with AcquireReleaseLock(lock=previous_context.conditional_variable):
                    execution_context.previous_context = previous_context

            execution_context.dispatch()  # execute task

            if task.is_conditional:
                if execution_context.execution_failed():
                    cls.execute_task(
                        task=task.on_failure_event,
                        previous_context=execution_context,
                        pipeline=pipeline,
                        sink_queue=sink_queue,
                    )
                else:
                    cls.execute_task(
                        task=task.on_success_event,
                        previous_context=execution_context,
                        pipeline=pipeline,
                        sink_queue=sink_queue,
                    )
            else:
                cls.execute_task(
                    task=task.on_success_event,
                    previous_context=execution_context,
                    pipeline=pipeline,
                    sink_queue=sink_queue,
                )

        else:
            # clear the sink nodes
            while sink_queue:
                task = sink_queue.popleft()
                cls.execute_task(
                    task=task,
                    previous_context=previous_context,
                    pipeline=pipeline,
                    sink_queue=sink_queue,
                )
