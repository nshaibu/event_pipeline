import typing

if typing.TYPE_CHECKING:
    from event_pipeline.base import EventBase
    from .task_group import TaskGroupingProtocol
    from .task import TaskProtocol
    from ..operator import PipeType
    from ..options import Options
    from ..conditional import ConditionalNode


class TaskProtocolMixin(typing.Protocol):
    """Mixin for Task protocol"""

    # options specified in pointy scripts for tasks are kept here
    options: typing.Optional["Options"]

    parent_node: typing.Optional[typing.Union["TaskProtocol", "TaskGroupingProtocol"]]

    # sink event this is where the conditional events collapse
    # into after they are done executing
    sink_node: typing.Optional[typing.Union["TaskProtocol", "TaskGroupingProtocol"]]
    sink_pipe: typing.Optional["PipeType"]

    condition_node: "ConditionalNode"

    def get_id(self) -> str:
        """Return task id"""

    @property
    def descriptor(self) -> int: ...

    @descriptor.setter
    def descriptor(self, value: int) -> None: ...

    @property
    def descriptor_pipe(self) -> "PipeType": ...

    @descriptor_pipe.setter
    def descriptor_pipe(self, value: "PipeType") -> None: ...

    @property
    def is_conditional(self) -> bool: ...

    @property
    def is_descriptor_task(self) -> bool: ...

    @property
    def is_sink(self) -> bool: ...

    @property
    def is_parallel_execution_node(self) -> bool: ...

    def get_root(self) -> "TaskProtocol": ...

    def get_task_pointer_type(self) -> typing.Optional["PipeType"]:
        """Return the pointer type pointing to this task"""

    def get_parent_node_for_parallel_execution(
        self,
    ) -> typing.Optional["TaskProtocol"]: ...

    def get_event_klass(self) -> "EventBase": ...

    def get_descriptor(self, descriptor: int) -> "TaskProtocol": ...
