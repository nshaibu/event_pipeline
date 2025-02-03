import typing
from collections import OrderedDict, deque
from enum import Enum, unique
from .base import EventBase
from . import parser
from .utils import generate_unique_id


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

        self.event = event
        self.on_success_event = on_success_event
        self.on_failure_event = on_failure_event
        self.on_success_pipe = on_success_pipe
        self.on_failure_pipe = on_failure_pipe

        self._execution_start_tp: int = 0
        self._execution_end_tp: int = 0

    @property
    def pk(self) -> str:
        return generate_unique_id(self)

    def __str__(self):
        return f"{self.event}:{self._state}"

    def __repr__(self):
        return f"{self.pk}({self.event}, [{repr(self.on_success_event)}, {repr(self.on_failure_event)}])"

    def __hash__(self):
        return hash(self.pk)

    def get_errors(self) -> typing.Dict[str, typing.Any]:
        error_dict = {"event_name": self.__class__.__name__.lower(), "errors": []}
        if self._errors:
            error_dict["errors"] = self._errors
            return error_dict
        return error_dict

    @staticmethod
    def get_event_klasses():
        yield from EventBase.get_event_klasses()

    @classmethod
    def build_pipeline_from_execution_code(cls, code: str):
        if not code:
            raise IndexError("No pointy code provided")

        ast = parser.pointy_parser(code)
        child_tasks = deque()

        task_node = None

        for token in parser.depth_first_traverse_post_order(ast):
            if isinstance(token, parser.TaskName):
                if task_node is None:
                    task_node = cls(event=token.value)
                else:
                    # store previous task before approaching the next operator
                    child_tasks.append(task_node)
                    task_node = cls(event=token.value)
            elif isinstance(token, parser.Descriptor):
                task_node = (task_node, token.value)
            elif isinstance(token, parser.ConditionalBinOP):
                parent = cls(event=token.parent.value)
                if task_node:
                    child_tasks.append(task_node)
                    task_node = None

                while child_tasks:
                    op, task, descriptor = child_tasks.popleft()
                    if descriptor == "0":
                        parent.on_failure_event = task
                        parent.on_failure_pipe = (
                            PipeType.POINTER
                            if op == PipeType.POINTER.token()
                            else PipeType.PIPE_POINTER
                        )
                    else:
                        parent.on_success_event = task
                        parent.on_success_pipe = (
                            PipeType.POINTER
                            if op == PipeType.POINTER.token()
                            else PipeType.PIPE_POINTER
                        )

                child_tasks.append(parent)
            elif isinstance(token, parser.BinOp):
                if isinstance(task_node, tuple):
                    # Add the operator to the processing tuple.
                    # it will be evaluated in the conditionals block
                    task_node = (token.op, *task_node)
                elif len(child_tasks) >= 2:
                    # Evaluate simple instruction here i.e A->B
                    left_node = child_tasks.popleft()
                    right_node = child_tasks.popleft()
                    right_node.on_success_event = left_node
                    right_node.on_success_pipe = (
                        PipeType.POINTER
                        if token.op == PipeType.POINTER.token()
                        else PipeType.PIPE_POINTER
                    )

                    child_tasks.append(right_node)

                    if task_node:
                        child_tasks.append(task_node)
                        task_node = None

        if child_tasks:
            return child_tasks.popleft()

        return task_node
