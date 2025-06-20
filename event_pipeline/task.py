import logging
import threading
import time
import typing
from dataclasses import dataclass, field
from functools import lru_cache
from collections import deque
from threading import Condition
from concurrent.futures import Executor, wait, Future
from enum import Enum, unique
from pydantic_mini import BaseModel, MiniAnnotated, Attrib
from .base import (
    EventBase,
    EventExecutionEvaluationState,
    EvaluationContext,
    ExecutorInitializerConfig,
)
from . import parser
from .constants import EMPTY
from .result import EventResult, ResultSet
from .exceptions import (
    PipelineError,
    BadPipelineError,
    ImproperlyConfigured,
    StopProcessingError,
    EventDoesNotExist,
    SwitchTask,
    TaskSwitchingError,
)
from .utils import (
    build_event_arguments_from_pipeline,
    get_function_call_args,
    AcquireReleaseLock,
)
from .signal.signals import (
    SoftSignal,
    event_execution_start,
    event_execution_end,
    event_execution_init,
    event_execution_aborted,
    event_execution_cancelled,
)
from .mixins import ObjectIdentityMixin
from .import_utils import import_string

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from .pipeline import Pipeline
    from .parser.ast import AssignmentExpressionGroup


def attach_signal_emitter(signal: SoftSignal, **signal_kwargs) -> None:
    signal.emit(**signal_kwargs)


class Options(BaseModel):
    retry_attempts: typing.Optional[int]
    executor: typing.Optional[str]
    executor_config: MiniAnnotated[dict, Attrib(default_factory=dict)]
    extras: MiniAnnotated[dict, Attrib(default_factory=dict)]
    execution_evaluation_state: typing.Optional[str]

    @classmethod
    def from_assigment_expression_group(
        cls, assigment_expression_group: "AssignmentExpressionGroup"
    ) -> "Options":
        fields = [
            "retry_attempts",
            "executor",
            "executor_config",
            "extras",
            "execution_evaluation_state",
        ]
        assignment_dict = {}
        for assignment in assigment_expression_group.assignment_groups():
            if assignment.variable in fields:
                assignment_dict[assignment.variable] = assignment.value
            else:
                if "extras" not in assignment.variable:
                    assignment_dict["extras"] = {}
                assignment_dict["extras"][assignment.variable] = assignment.value

        return cls.loads(assignment_dict, _format="dict")


class ExecutionState(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    CANCELLED = "cancelled"
    FINISHED = "finished"
    ABORTED = "aborted"


class EventExecutionContext(ObjectIdentityMixin):

    def __init__(
        self,
        task: typing.Union["PipelineTask", typing.List["PipelineTask"]],
        pipeline: "Pipeline",
    ):
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


        Details:
            Represents the execution context of the pipeline as a bidirectional (doubly-linked) list.
            Each node corresponds to an event's execution context, allowing traversal both forward and backward
            through the pipeline's events.

            You can filter contexts by event name using the `filter_by_event` method.

            The context is iterable in the forward direction, so you can loop through it like this:
                for context in pipeline.start():
                    pass

            To access specific ends of the context queue:
            - Use `get_execution_context_head()` to retrieve the head (starting context).
            - Use `get_tail_context()` to retrieve the tail (ending context).

            Reverse traversal can be done by walking backward from the tail using the linked structure.
        """

        super().__init__()
        self.conditional_variable = Condition()

        self._execution_start_tp: float = time.time()
        self._execution_end_tp: float = 0
        self.task_profiles = task if isinstance(task, (tuple, list)) else [task]
        self.pipeline = pipeline
        self.execution_result: ResultSet = ResultSet([])
        self.state: ExecutionState = ExecutionState.PENDING

        self.previous_context: typing.Optional[EventExecutionContext] = None
        self.next_context: typing.Optional[EventExecutionContext] = None

        self._errors: typing.List[PipelineError] = []

    def __iter__(self):
        current = self
        while current is not None:
            yield current
            current = current.next_context

    @staticmethod
    def _configure_event(event: EventBase, profile: "PipelineTask"):
        number_of_retries = profile.extra_config.number_of_retries or 0
        options_retries = profile.options and profile.options.retry_attempts or 0
        total_retries = number_of_retries + options_retries
        if total_retries > 1:
            event_retry_policy = event.get_retry_policy()
            if event_retry_policy:
                event_retry_policy.max_attempts = total_retries
            else:
                event.config_retry_policy(max_attempts=total_retries)

    @staticmethod
    def _get_task_executor_klass(task: "PipelineTask") -> typing.Type[Executor]:
        if task.options:
            executor_str = task.options.executor
            if executor_str is not None:
                try:
                    instance = import_string(executor_str)
                    if not issubclass(instance, Executor):
                        raise ValueError(f"Unsupported executor type {executor_str}")
                    return instance
                except ImportError:
                    logger.warning("Could not import executor %s", executor_str)
                except ValueError as e:
                    logger.warning(str(e))
        return PipelineTask.resolve_event_name(task.event).get_executor_class()

    @staticmethod
    def _get_task_executor_config(
        task: "PipelineTask", event: EventBase
    ) -> typing.Dict[str, typing.Any]:
        executor_config = None
        if task.options:
            executor_config = task.options.executor_config
            if executor_config is not None:
                if not isinstance(executor_config, dict):
                    logger.warning(
                        "Unsupported executor config type '%s'",
                        executor_config,
                    )

        return event.get_executor_context(params=executor_config)

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
            executor = self._get_task_executor_klass(task)

            self._configure_event(event, task)

            event_execution_init.emit(
                sender=self.__class__,
                event=event,
                execution_context=self,
                executor=executor,
                call_kwargs=event_call_args,
            )

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
        state.pop("conditional_variable", None)
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
        state["conditional_variable"] = threading.Condition()
        self.__dict__.update(state)

    def __hash__(self):
        return hash(self.id)

    def execution_failed(self):
        with self.conditional_variable:
            if self.state in [ExecutionState.CANCELLED, ExecutionState.ABORTED]:
                return True
            evaluator = self._get_execution_state_evaluator()
            return evaluator.context_evaluation(
                self.execution_result, self._errors, context=EvaluationContext.FAILURE
            )

    def execution_success(self):
        with self.conditional_variable:
            if self.state in [ExecutionState.CANCELLED, ExecutionState.ABORTED]:
                return False
            evaluator = self._get_execution_state_evaluator()
            return evaluator.context_evaluation(
                self.execution_result, self._errors, context=EvaluationContext.SUCCESS
            )

    def _submit_event_to_executor(
        self, executor: Executor, event_config: typing.Dict[str, typing.Any]
    ) -> Future:
        """
        Submits an event for execution by the provided executor.

        Args:
            executor (Executor): The executor responsible for running the event task.
                This could be a ThreadPoolExecutor, ProcessPoolExecutor, or any other
                executor implementing the 'Executor' interface.
            event_config (dict): A dictionary containing data for the event.

        Returns:
            Future
        """

        event_execution_start.emit(
            sender=self.__class__,
            event=event_config["event"],
            execution_context=self,
        )

        future = executor.submit(event_config["event"], **event_config["call_args"])
        future.add_done_callback(
            lambda fut: attach_signal_emitter(
                signal=event_execution_end,
                sender=self.__class__,
                event=event_config["event"],
                execution_context=self,
            )
        )
        return future

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
                    future = self._submit_event_to_executor(executor, event_config)
                    futures.append(future)
            else:
                # parallel execution with common executor
                with executor_klass(**executor_klass_config) as executor:
                    for _, event_config in execution_config.items():
                        future = self._submit_event_to_executor(executor, event_config)
                        futures.append(future)

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
        executor_klass = self._get_task_executor_klass(task_profile)
        if not issubclass(executor_klass, Executor):
            raise ImproperlyConfigured(
                f"Event executors must implement the 'concurrent.futures.Executor' interface"
            )

        logger.info(f"Executing event '{task_profile.event}'")

        event_init_arguments, event_call_arguments = (
            build_event_arguments_from_pipeline(event_klass, self.pipeline)
        )

        event_init_arguments = event_init_arguments or {}
        event_call_arguments = event_call_arguments or {}

        event_init_arguments["execution_context"] = self
        event_init_arguments["task_id"] = task_profile.id

        # Let's pass the options given in the pointy script to the event
        if task_profile.options:
            event_init_arguments["options"] = task_profile.options

        if task_profile.is_parallel_execution_node:
            parent = task_profile.get_parallel_execution_parent_node()
            pointer_type = parent.get_pointer_type_to_this_event()
        else:
            pointer_type = task_profile.get_pointer_type_to_this_event()

        if pointer_type == PipeType.PIPE_POINTER:
            if self.previous_context:
                event_init_arguments["previous_result"] = (
                    self.previous_context.execution_result
                )
            else:
                event_init_arguments["previous_result"] = EMPTY

        event = event_klass(**event_init_arguments)

        context = self._get_task_executor_config(task=task_profile, event=event)
        context = get_function_call_args(executor_klass.__init__, context)

        return event, context, event_call_arguments

    def _get_last_task_profile_in_chain(self) -> "PipelineTask":
        """
        Retrieves the last task profile in the chain of task profiles.

        This method examines the list of task profiles to identify the last task in
        a pipeline. If there is only one task profile, it returns that profile directly.
        For multiple task profiles, it iterates through each profile and checks the
        pointer type associated with the event. Specifically, it looks for a task
        profile whose pointer type indicates parallelism (PipeType.PARALLELISM) and
        ensures that its on-success pipe type is not parallelism. This helps in
        identifying the last task in a sequence when tasks are executed in parallel
        followed by a task that depends on the success of those parallel tasks.

        Returns:
            PipelineTask: The last task profile in the chain or the single task profile
                           if only one exists.
        """
        if len(self.task_profiles) == 1:
            return self.task_profiles[0]
        for task_profile in self.task_profiles:
            pointer_to_task = task_profile.get_pointer_type_to_this_event()
            if (
                pointer_to_task == PipeType.PARALLELISM
                and task_profile.on_success_pipe != PipeType.PARALLELISM
            ):
                return task_profile

    def _get_execution_state_evaluator(self) -> EventExecutionEvaluationState:
        # For parallel execution, we use the evaluator of the last task in the chain
        # i.e for A||B||C, we will use the evaluator of 'C'
        task_profile = self._get_last_task_profile_in_chain()
        if task_profile.options:
            evaluator_str = task_profile.options.execution_evaluation_state
            if evaluator_str:
                evaluator = getattr(EventExecutionEvaluationState, evaluator_str, None)
                if evaluator:
                    return evaluator
                else:
                    logger.warning(
                        "Could not find an evaluator for '%s' failing back to event configured evaluator",
                        evaluator_str,
                    )
        return task_profile.get_event_klass().execution_evaluation_state

    def dispatch(self):
        """
        Dispatches an action or event to the appropriate handler or process.

        This method is responsible for routing the event or action to the correct
        handler based on the context, ensuring that the proper logic is executed
        for the given task or event.
        """
        switch_exception = None

        try:
            self.state = ExecutionState.EXECUTING

            self.process_executor_results(self.init_and_execute_events())

            if self.state == ExecutionState.EXECUTING:
                self.state = ExecutionState.FINISHED
        except Exception as e:
            logger.error(
                f"{self.pipeline.__class__.__name__} : {str(self.task_profiles[0].event)} : {str(e)}"
            )

            if isinstance(e, SwitchTask):
                switch_exception = e
            else:
                task_error = BadPipelineError(
                    message={"status": 0, "message": str(e)},
                    exception=e,
                )
                self._errors.append(task_error)
                self.abort()

        try:
            self.conditional_variable.notify_all()
        except RuntimeError:
            pass

        self._execution_end_tp = time.time()

        logger.info(
            f"Finished executing task(s) '{self.task_profiles}' with status {self.state}"
        )

        return switch_exception

    def process_executor_results(self, futures: typing.List[Future]) -> None:
        """
        Processes the results from the executor after events has been executed, handling any awaited results.

        Args:
            futures (typing.List[Future]): The results that were awaited during execution, which need to be processed.

        Returns:
            None: This method modifies internal states of the execution context and performs actions based on
             the event and results, without returning a value.
        """
        last_switch_to_task_request = None
        waited_results = wait(futures)

        with AcquireReleaseLock(self.conditional_variable):

            for fut in waited_results.done:
                try:
                    result: EventResult = fut.result()
                except Exception as e:
                    if isinstance(e, SwitchTask):
                        result = e.result
                        current_task_profile = self._get_last_task_profile_in_chain()
                        if not current_task_profile.extra_config.get_descriptor_config(
                            e.next_task_descriptor
                        ):
                            logger.error(
                                f"Task profile has no configured descriptor {e.next_task_descriptor}"
                            )
                            self.cancel()
                            e.descriptor_configured = False
                        else:
                            e.descriptor_configured = True
                        last_switch_to_task_request = e
                    else:
                        params = getattr(e, "params", {})
                        event_name = params.get("event_name", "unknown")

                        logger.error(
                            f"{self.pipeline.__class__.__name__} : {event_name} : {str(e)}"
                        )

                        if e.__class__ == StopProcessingError:
                            self.cancel()

                        result = EventResult(
                            error=True,
                            content=e.to_dict() if hasattr(e, "to_dict") else str(e),
                            task_id=params.get("task_id"),
                            event_name=event_name,
                            init_params=params.get("init_args"),
                            call_params=params.get("call_args"),
                        )

                if result.error:
                    self._errors.append(
                        PipelineError(
                            message=result.content,
                            code=result.task_id,
                            params=result.as_dict(),
                        )
                    )
                else:
                    self.execution_result.add(result)

        if last_switch_to_task_request:
            raise last_switch_to_task_request

    def cancel(self):
        """
        Cancels the execution context. This method must acquire
        the conditional variable before executing it.
        """
        self.state = ExecutionState.CANCELLED
        event_execution_cancelled.emit(
            sender=self.__class__,
            task_profiles=self.task_profiles,
            execution_context=self,
            state=self.state,
        )

    def abort(self):
        """
        Aborts the execution context. This method must acquire the
        conditional variable before executing it.
        """
        self.state = ExecutionState.ABORTED
        event_execution_aborted.emit(
            sender=self.__class__,
            task_profiles=self.task_profiles,
            execution_context=self,
            state=self.state,
        )

    def get_execution_context_head(self) -> "EventExecutionContext":
        """
        Returns the execution context head of the execution context.
        :return: ExecutionContext head of the execution context.
        """
        current = self
        while current.previous_context:
            current = current.previous_context
        return current

    def get_latest_execution_context(self) -> "EventExecutionContext":
        """
        Returns the latest execution context.
        :return: EventExecutionContext
        """
        current = self.get_execution_context_head()
        while current.next_context:
            current = current.next_context
        return current

    def get_tail_context(self) -> "EventExecutionContext":
        """
        Returns the tail context of the execution context.
        :return: EventExecutionContext
        """
        return self.get_latest_execution_context()

    def filter_by_event(self, event_name: str) -> ResultSet:
        """
        Filters the execution context based on the event name.
        :param event_name: Case-insensitive event name.
        :return: ResultSet with the filtered execution context.
        """
        head = self.get_execution_context_head()
        event = PipelineTask.resolve_event_name(event_name)
        result = ResultSet([])

        for context in head:
            if event in [task.event for task in context.task_profiles]:
                result.add(context)
        return result


@dataclass
class _DescriptorConfig:
    descriptor: int
    pipe: "PipeType"
    task: "PipelineTask"


@dataclass
class ExtraPipelineTaskConfig:
    number_of_retries: int = field(init=True, default=None)
    _descriptors: typing.Dict[int, _DescriptorConfig] = field(
        init=False, repr=False, default_factory=dict
    )

    def add_descriptor(self, descriptor: int, pipe: "PipeType", task: "PipelineTask"):
        if 1 < descriptor < 10:
            self._descriptors[descriptor] = _DescriptorConfig(
                pipe=pipe, task=task, descriptor=descriptor
            )
            return True
        return False

    def get_descriptor_config(self, descriptor: int):
        return self._descriptors.get(descriptor)

    def get_descriptors(self) -> typing.List["_DescriptorConfig"]:
        return list(self._descriptors.values())


@unique
class PipeType(Enum):
    POINTER = "pointer"
    PIPE_POINTER = "pipe_pointer"
    PARALLELISM = "parallelism"
    RETRY = "retry"

    def token(self):
        if self == self.POINTER:
            return "->"
        elif self == self.PIPE_POINTER:
            return "|->"
        elif self == self.PARALLELISM:
            return "||"
        elif self == self.RETRY:
            return "*"

    @classmethod
    def get_pipe_type_enum(cls, pipe_str: str) -> "PipeType":
        if pipe_str == cls.PIPE_POINTER.token():
            return cls.PIPE_POINTER
        elif pipe_str == cls.PARALLELISM.token():
            return cls.PARALLELISM
        elif pipe_str == cls.RETRY.token():
            return cls.RETRY
        elif pipe_str == cls.POINTER.token():
            return cls.POINTER


class PipelineTask(ObjectIdentityMixin):
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
        super().__init__()

        self.extra_config: ExtraPipelineTaskConfig = ExtraPipelineTaskConfig()

        # options specified in pointy scripts for tasks are kept here
        self.options: typing.Optional[Options] = None

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

    def __str__(self):
        return self.event

    def __repr__(self):
        return f"{self.__class__.__name__}<{self.event}>"

    def __hash__(self):
        return hash(self.id)

    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    @property
    def is_conditional(self):
        if self.extra_config.get_descriptors():
            return True
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

    @property
    def is_parallel_execution_node(self):
        """
        Determines whether the current node is configured for parallel execution.

        This method evaluates whether the current node is configured for parallel execution by
        checking two conditions:
        1. It verifies if the `on_success_pipe` of the current node is set to `PipeType.PARALLELISM`.
        2. It retrieves the pointer type to this event and checks if it is also `PipeType.PARALLELISM`.

        If either of these conditions is true, the method returns True, indicating that parallel execution
        is applicable; otherwise, it returns False.
        """

        pointer_to_node = self.get_pointer_type_to_this_event()
        return (
            self.on_success_pipe == PipeType.PARALLELISM
            or pointer_to_node == PipeType.PARALLELISM
        )

    def get_parallel_nodes(self):
        if not self.is_parallel_execution_node:
            return

        parallel_tasks = deque()
        task = self
        while task and task.on_success_pipe == PipeType.PARALLELISM:
            parallel_tasks.append(task)
            task = task.on_success_event

        parallel_tasks.append(task)
        return parallel_tasks

    def get_parallel_execution_parent_node(self):
        if self.is_parallel_execution_node:
            if (
                self.parent_node
                and self.parent_node.on_success_pipe == PipeType.PARALLELISM
            ):
                return self.parent_node.get_parallel_execution_parent_node()
            else:
                return self

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
    def build_pipeline_from_execution_code(cls, code: str) -> "PipelineTask":
        """
        Constructs a pipeline based on the provided execution code.

        This method parses and processes the given execution code to build a corresponding pipeline
        that can be executed within the system.

        Args:
            code (str): The execution code as a string, typically representing a sequence of
                        operations or instructions to construct the pipeline.

        Returns:
            PipelineTask: The constructed pipeline based on the provided execution code.

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
                    # handle retry syntax
                    if ast.op == PipeType.RETRY.token():
                        node.extra_config.number_of_retries = descriptor_value
                        return node

                    node = node.get_root()
                    node._descriptor = descriptor_value
                    node._descriptor_pipe = ast.op
                    return node
                # TODO : Better error message
                raise SyntaxError(f"AST is malformed {ast}")
            else:
                return left_node or right_node
        elif isinstance(ast, parser.TaskName):
            instance = cls(event=ast.value)
            if ast.options:
                instance.options = Options.from_assigment_expression_group(ast.options)
            return instance
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
                        parent.on_failure_pipe = PipeType.get_pipe_type_enum(
                            node._descriptor_pipe
                        )
                    else:
                        parent.on_success_event = node
                        parent.on_success_pipe = PipeType.get_pipe_type_enum(
                            node._descriptor_pipe
                        )

            for custom_node in ast.extra_descriptors():
                custom_branch = cls._parse_ast(custom_node)
                if custom_branch:
                    head_of_custom_branch = custom_branch.get_root()
                    head_of_custom_branch.parent_node = parent
                    status = parent.extra_config.add_descriptor(
                        custom_node.left.value,
                        PipeType.get_pipe_type_enum(custom_node.op),
                        head_of_custom_branch,
                    )
                    if status is False:
                        logger.warning(f"Adding descriptor {custom_node} failed.")

            return parent
        elif isinstance(ast, parser.Descriptor):
            return int(ast.value)
        elif isinstance(ast, int):
            return ast

    def get_children(self):
        children = []
        if self.on_failure_event:
            children.append(self.on_failure_event)
        if self.sink_node:
            children.append(self.sink_node)
        if self.on_success_event:
            children.append(self.on_success_event)
        for node_config in self.extra_config.get_descriptors():
            children.append(node_config.task)
        return children

    def get_root(self):
        if self.parent_node is None:
            return self
        return self.parent_node.get_root()

    def get_dot_node_data(self) -> typing.Optional[str]:
        if self.is_sink:
            return f'\t"{self.id}" [label="{self.event}", shape=box, style="filled,rounded", fillcolor=yellow]\n'
        elif self.is_conditional:
            return f'\t"{self.id}" [label="{self.event}", shape=diamond, style="filled,rounded", fillcolor=yellow]\n'
        elif self.is_parallel_execution_node:
            nodes = self.get_parallel_nodes()
            if not nodes:
                return
            node_id = nodes[0].id
            node_label = "{" + "|".join([n.event for n in nodes]) + "}"
            return f'\t"{node_id}" [label="{node_label}", shape=record, style="filled,rounded", fillcolor=lightblue]\n'

        return f'\t"{self.id}" [label="{self.event}", shape=circle, style="filled,rounded", fillcolor=yellow]\n'

    def get_task_count(self) -> int:
        root = self.get_root()
        nodes = list(self.bf_traversal(root))
        return len(nodes)

    def get_descriptor(self, descriptor: int) -> typing.Optional["PipelineTask"]:
        if descriptor in [0, 1]:
            return self.on_failure_event if descriptor == 0 else self.on_success_event
        target = self.extra_config.get_descriptor_config(descriptor)
        if target:
            return target.task

    @classmethod
    def bf_traversal(cls, node: "PipelineTask"):
        if node:
            yield node

            for child in node.get_children():
                yield from cls.bf_traversal(child)

    def get_pointer_type_to_this_event(self) -> PipeType:
        pipe_type = None
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
            else:
                # Handle custom descriptors
                descriptor_profile = (
                    self.parent_node.extra_config.get_descriptor_config(
                        self._descriptor
                    )
                )
                if descriptor_profile:
                    pipe_type = descriptor_profile.pipe
                else:
                    pipe_type = self._descriptor_pipe

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
                    previous_context.next_context = execution_context

            switch_request = execution_context.dispatch()  # execute task

            if execution_context and execution_context.state in [
                ExecutionState.CANCELLED,
                ExecutionState.ABORTED,
            ]:
                logger.warning(
                    f"Task execution terminated due to state '{execution_context.state.value}'."
                    f"\n Skipping task execution..."
                )
                return

            if switch_request and switch_request.descriptor_configured:
                task_profile = task.get_descriptor(switch_request.next_task_descriptor)
                if task_profile is None:
                    logger.warning(
                        f"Task cannot switch to task with the descriptor {switch_request.next_task_descriptor}."
                    )
                    raise TaskSwitchingError(
                        f"Task cannot switch to task using the descriptor {switch_request.next_task_descriptor}.",
                        params=switch_request,
                        code="task-switching-failed",
                    )

                cls.execute_task(
                    task=task_profile,
                    pipeline=pipeline,
                    previous_context=previous_context,
                    sink_queue=sink_queue,
                )
            else:
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
                task = sink_queue.pop()
                cls.execute_task(
                    task=task,
                    previous_context=previous_context,
                    pipeline=pipeline,
                    sink_queue=sink_queue,
                )
