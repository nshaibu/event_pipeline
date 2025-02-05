import typing

PIPELINE_FIELDS = "__pipeline_fields__"

PIPELINE_STATE = "_state"

UNKNOWN = object()


class EMPTY:
    pass


class EventResult(typing.NamedTuple):
    is_error: bool
    detail: typing.Union[typing.Dict[str, typing.Any], typing.Type[Exception], str]
    task_id: typing.Union[int, str] = None
