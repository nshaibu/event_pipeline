import typing

from .mixin import TaskProtocolMixin


@typing.runtime_checkable
class TaskProtocol(TaskProtocolMixin, typing.Protocol):
    """Individual task protocol."""

    event: typing.Union["TaskProtocol", str]

    def __init__(
        self,
        event: typing.Union[typing.Type["EventBase"], str],
    ) -> None: ...
