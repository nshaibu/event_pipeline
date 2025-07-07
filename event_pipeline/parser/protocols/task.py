import typing


@typing.runtime_checkable
class TaskProtocol(typing.Protocol):
    """Individual task protocol."""

    extra_config: "ExtraPipelineTaskConfig"

    # options specified in pointy scripts for tasks are kept here
    options: typing.Optional["Options"]

    event: typing.Union["TaskProtocol", str]
    parent: typing.Optional["TaskProtocol"]

    # conditional events
    on_success_event: typing.Optional["TaskProtocol"]
    on_failure_event: typing.Optional["TaskProtocol"]
    on_success_pipe: typing.Optional["TaskProtocol"]
    on_failure_pipe: typing.Optional["TaskProtocol"]

    def __init__(
        self,
        event: typing.Union[typing.Type["EventBase"], str],
        on_success_event: typing.Optional["TaskProtocol"] = None,
        on_failure_event: typing.Optional["TaskProtocol"] = None,
        on_success_pipe: typing.Optional["PipeType"] = None,
        on_failure_pipe: typing.Optional["PipeType"] = None,
    ) -> None: ...

    @property
    def descriptor(self) -> int: ...

    @descriptor.setter
    def descriptor(self, value: int) -> None: ...

    @property
    def descriptor_pipe(self) -> "PipeType": ...

    @descriptor_pipe.setter
    def descriptor_pipe(self, value: "PipeType") -> None: ...

    @property
    def is_conditional(self) -> "TaskProtocol": ...

    @property
    def is_descriptor_task(self) -> "TaskProtocol": ...

    @property
    def is_sink(self) -> "TaskProtocol": ...

    @property
    def is_parallel_execution_node(self): ...

    def get_root(self) -> "TaskProtocol": ...
