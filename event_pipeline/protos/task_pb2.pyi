from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TaskRequest(_message.Message):
    __slots__ = ("task_id", "fn", "name", "args", "kwargs")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    FN_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    KWARGS_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    fn: bytes
    name: str
    args: bytes
    kwargs: bytes
    def __init__(
        self,
        task_id: _Optional[str] = ...,
        fn: _Optional[bytes] = ...,
        name: _Optional[str] = ...,
        args: _Optional[bytes] = ...,
        kwargs: _Optional[bytes] = ...,
    ) -> None: ...

class TaskResponse(_message.Message):
    __slots__ = ("success", "result", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    result: bytes
    error: str
    def __init__(
        self,
        success: bool = ...,
        result: _Optional[bytes] = ...,
        error: _Optional[str] = ...,
    ) -> None: ...

class TaskStatus(_message.Message):
    __slots__ = ("status", "result", "message")

    class Status(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        PENDING: _ClassVar[TaskStatus.Status]
        RUNNING: _ClassVar[TaskStatus.Status]
        COMPLETED: _ClassVar[TaskStatus.Status]
        FAILED: _ClassVar[TaskStatus.Status]

    PENDING: TaskStatus.Status
    RUNNING: TaskStatus.Status
    COMPLETED: TaskStatus.Status
    FAILED: TaskStatus.Status
    STATUS_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    status: TaskStatus.Status
    result: bytes
    message: str
    def __init__(
        self,
        status: _Optional[_Union[TaskStatus.Status, str]] = ...,
        result: _Optional[bytes] = ...,
        message: _Optional[str] = ...,
    ) -> None: ...
