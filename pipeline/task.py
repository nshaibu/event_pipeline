import typing
from collections import OrderedDict, deque
from enum import Enum, unique
from .base import EventBase
from . import parser


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

    def __str__(self):
        return f"{self.event}:{self._state}"

    def __repr__(self):
        return f"{self.__class__}({self.event}, ({repr(self.on_success_event)}, {repr(self.on_failure_event)}))"

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
    def _resolve_event_name(cls, event_name: str) -> typing.Type[EventBase]:
        for event in cls.get_event_klasses():
            klass_name = event.__name__.lower()
            if klass_name == event_name:
                return event
        raise EventDoesNotExist(f"'{event_name}' was not found.")

    @classmethod
    def process_event_name(cls, name: str):
        value = name.split(" ")
        if len(value) == 1:
            return cls._resolve_event_name(name), None
        return cls._resolve_event_name(value[0]), [
            OrderedDict(
                [
                    (klass, cls._resolve_event_name(klass))
                    for klass in value[1].split(",")
                ]
            )
        ]

    @classmethod
    def process_task_info_map(cls, task, task_map):
        if task.event != task_map["task"].event:
            if "on_failure_pipe" in task_map:
                task.on_failure_event = task_map["task"]
                task.on_failure_pipe = (
                    PipeType.POINTER
                    if task_map["op"] == PipeType.POINTER.token()
                    else PipeType.PIPE_POINTER
                )
            else:
                task.on_success_event = task_map["task"]
                task.on_failure_pipe = (
                    PipeType.POINTER
                    if task_map["op"] == PipeType.POINTER.token()
                    else PipeType.PIPE_POINTER
                )
        return task

    @classmethod
    def build_pipeline_from_execution_code(cls, code: str):
        ast = parser.pointy_parser(code)
        child_tasks = deque()

        task_node = None
        import pdb;pdb.set_trace()

        for token in parser.depth_first_traverse_post_order(ast):
            if isinstance(token, parser.TaskName):
                if task_node is None:
                    task_node = cls(event=token.value)
                else:
                    # store previous task before approaching the operator
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
                    # child_tasks.append(task_node)
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

        print(child_tasks)

        return child_tasks.popleft()

        # task_info_queue = deque()
        # task_info_map = None
        # import pdb;pdb.set_trace()
        # for token in parser.depth_first_traverse_post_order(ast):

        #     if isinstance(token, parser.TaskName):
        #         new_task = cls(token.value)
        #         if task_info_map is None:
        #             task_info_map = dict()
        #
        #         if task_info_queue:
        #             task_info_map = task_info_queue.popleft()
        #             if all([key not in task_info_map for key in ["on_failure_pipe", "on_success_pipe"]]):
        #                 new_task = cls.process_task_info_map(new_task, task_info_map)
        #
        #         task_info_map["task"] = new_task
        #     elif isinstance(token, parser.Descriptor):
        #         task_info_map = dict()
        #         if token.value == "0":
        #             task_info_map["on_failure_pipe"] = "0"
        #         else:
        #             task_info_map["on_success_pipe"] = "1"
        #     elif isinstance(token, parser.BinOp):
        #         task_info_map["op"] = token.op
        #         task_info_queue.append(task_info_map)
        #     elif isinstance(token, parser.ConditionalBinOP):
        #         new_task = cls(token.parent.value)
        #
        #         for task_map in task_info_queue:
        #             if "on_failure_pipe" in task_map:
        #                 new_task.on_failure_event = task_map["task"]
        #                 new_task.on_failure_pipe = (
        #                     PipeType.POINTER
        #                     if task_map["op"] == PipeType.POINTER.token()
        #                     else PipeType.PIPE_POINTER
        #                 )
        #             else:
        #                 new_task.on_success_event = task_map["task"]
        #                 new_task.on_failure_pipe = (
        #                     PipeType.POINTER
        #                     if task_map["op"] == PipeType.POINTER.token()
        #                     else PipeType.PIPE_POINTER
        #                 )
        #
        #         task_info_map["task"] = new_task
        #
        # # Consume the right task info
        # head = cls(event=ast.right.value)
        # while task_info_queue:
        #     task_map = task_info_queue.popleft()
        #     if head.event != task_map["task"].event:
        #         if "on_failure_pipe" in task_map:
        #             head.on_failure_event = task_map["task"]
        #             head.on_failure_pipe = (
        #                 PipeType.POINTER
        #                 if task_map["op"] == PipeType.POINTER.token()
        #                 else PipeType.PIPE_POINTER
        #             )
        #         else:
        #             head.on_success_event = task_map["task"]
        #             head.on_failure_pipe = (
        #                 PipeType.POINTER
        #                 if task_map["op"] == PipeType.POINTER.token()
        #                 else PipeType.PIPE_POINTER
        #             )
        #
        # return head
