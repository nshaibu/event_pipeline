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

        self._execution_start_tp: int = 0
        self._execution_end_tp: int = 0

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
        if parent:
            return parent.sink_node is not None
        return False

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

    @classmethod
    def bf_traversal(cls, node: "PipelineTask"):
        if node:
            yield node

            for child in node.get_children():
                yield from cls.bf_traversal(child)
