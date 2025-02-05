import logging
import time
import typing
from functools import lru_cache
from collections import deque
from concurrent.futures import Executor, wait
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
from .utils import build_event_arguments_from_pipeline, get_function_call_args

logger = logging.getLogger(__name__)


class ExecutionState(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    CANCELLED = "cancelled"
    FINISHED = "finished"
    ABORTED = "aborted"


class EventExecutionContext(object):

    def __init__(self, task: "PipelineTask", pipeline: "Pipeline"):
        generate_unique_id(self)

        self._execution_start_tp: float = time.time()
        self._execution_end_tp: float = 0
        self.task_profile = task
        self.pipeline = pipeline
        self.execution_result: typing.List[EventResult] = []
        self.state: ExecutionState = ExecutionState.PENDING

        self.previous_context: typing.Optional[EventExecutionContext] = None
        self.next_context: typing.Optional[EventExecutionContext] = None

        self._errors: typing.List[PipelineError] = []

    def execution_failed(self):
        if self.state in [ExecutionState.CANCELLED, ExecutionState.ABORTED]:
            return True
        return self._errors

    def execution_success(self):
        if self.state in [ExecutionState.CANCELLED, ExecutionState.ABORTED]:
            return False
        return not self._errors and self.execution_result

    def dispatch(self):
        event_klass = self.task_profile.get_event_klass()
        if not issubclass(event_klass.get_executor_class(), Executor):
            raise ImproperlyConfigured(f"Event executor must inherit {Executor}")

        try:
            # import pdb;pdb.set_trace()
            self.state = ExecutionState.EXECUTING

            logger.info(f"Executing event '{self.task_profile.event}'")

            event_init_arguments, event_call_arguments = (
                build_event_arguments_from_pipeline(event_klass, self.pipeline)
            )

            event_init_arguments = event_init_arguments or {}
            event_call_arguments = event_call_arguments or {}

            event_init_arguments["execution_context"] = self

            pointer_type = self.task_profile.get_pointer_type_to_this_event()
            if pointer_type != PipeType.POINTER:
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

            with executor_klass(**context) as executor:
                future = executor.submit(event, **event_call_arguments)

                waited_results = wait([future])
                self._execution_end_tp = time.time()

            for fut in waited_results.done:
                try:
                    result = fut.result()
                except Exception as e:
                    logger.exception(f"{event.__class__.__name__}: {str(e)}")
                    if isinstance(e, StopProcessingError):
                        self.state = ExecutionState.CANCELLED

                    result = EventResult(
                        is_error=True,
                        detail=str(e),
                        task_id=self.task_profile.id,
                        init_params=event.get_init_args(),
                        call_params=event.get_call_args(),
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

            self.state = ExecutionState.FINISHED
        except Exception as e:
            self.state = ExecutionState.ABORTED
            task_error = BadPipelineError(
                message={"status": 0, "message": str(e)},
                exception=e,
            )
            self._errors.append(task_error)

        logger.info(
            f"Finished executing task '{self.task_profile.event}' with status {self.state}"
        )


@unique
class TaskState(Enum):
    INITIALISED = "INITIALISED"
    READY = "ready"


@unique
class PipeType(Enum):
    POINTER = "pointer"
    PIPE_POINTER = "pipe_pointer"

    def token(self):
        if self == self.POINTER:
            return "->"
        elif self == self.PIPE_POINTER:
            return "|->"


class PipelineTask(object):

    def __init__(
        self,
        event: typing.Type[EventBase] | str,
        on_success_event: typing.Optional["PipelineTask"] = None,
        on_failure_event: typing.Optional["PipelineTask"] = None,
        on_success_pipe: typing.Optional[PipeType] = None,
        on_failure_pipe: typing.Optional[PipeType] = None,
    ):
        generate_unique_id(self)

        self._task = None
        self._errors: typing.List = []
        self._state: TaskState = TaskState.INITIALISED

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
        return f"{self.event}:{self._state}"

    def __repr__(self):
        return f"{self.event} -> [{repr(self.on_success_event)}, {repr(self.on_failure_event)}]"

    def __hash__(self):
        return hash(self.id)

    @property
    def is_conditional(self):
        return self.on_success_event and self.on_failure_event

    @property
    def is_descriptor_task(self):
        return self._descriptor is not None or self._descriptor_pipe is not None

    @property
    def is_sink(self) -> bool:
        parent = self.parent_node
        if parent and not self.is_descriptor_task:
            return parent.sink_node == self
        return False

    def get_event_klass(self):
        return self.resolve_event_name(self.event)

    def get_errors(self) -> typing.Dict[str, typing.Any]:
        error_dict = {"event_name": self.__class__.__name__.lower(), "errors": []}
        if self._errors:
            error_dict["errors"] = self._errors
            return error_dict
        return error_dict

    @classmethod
    @lru_cache()
    def resolve_event_name(cls, event_name: str) -> typing.Type[EventBase]:
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
        if not code:
            raise IndexError("No pointy code provided")

        ast = parser.pointy_parser(code)
        tail = cls._parse_ast(ast)
        return tail.get_root()

    @classmethod
    def _parse_ast(cls, ast):
        """
        TODO: add comment to explain the algorithm
        :param ast:
        :return:
        """
        if isinstance(ast, parser.BinOp):
            left_node = cls._parse_ast(ast.left)
            right_node = cls._parse_ast(ast.right)

            if isinstance(left_node, PipelineTask) and isinstance(
                right_node, PipelineTask
            ):
                pipe_type = (
                    PipeType.POINTER
                    if ast.op == PipeType.POINTER.token()
                    else PipeType.PIPE_POINTER
                )

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
                raise SyntaxError
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
        if task:
            if previous_context is None:
                execution_context = EventExecutionContext(pipeline=pipeline, task=task)
                pipeline.execution_context = execution_context
            elif task.is_sink:
                sink_queue.append(task)
                execution_context = EventExecutionContext(pipeline=pipeline, task=task)
                execution_context.previous_context = previous_context
            else:
                execution_context = EventExecutionContext(pipeline=pipeline, task=task)
                execution_context.previous_context = previous_context

            execution_context.dispatch()

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
