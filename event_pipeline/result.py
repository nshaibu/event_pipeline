import typing
from abc import ABC
from collections.abc import MutableSet
from .constants import EMPTY
from .utils import generate_unique_id

__all__ = ["EventResult", "ResultSet"]

EventResultInitVar = typing.TypeVar(
    "EventResultInitVar",
    typing.Dict[str, typing.Any],
    typing.Tuple[typing.Any],
    typing.Type[EMPTY],
)


class Result(object):

    def __init__(self, error, content: typing.Any, content_type: typing.Type = None):
        generate_unique_id(self)

        self.error: bool = error
        self.content: typing.Any = content
        self._content_type: typing.Type = (
            type(content) if content_type is not None else content_type
        )
        self._content_processors: typing.List[typing.Callable] = []

    @property
    def id(self) -> str:
        return generate_unique_id(self)

    def __hash__(self):
        return hash(self.id)

    @staticmethod
    def _resolve_list(value: typing.Collection, type_: typing.Type) -> typing.Any:
        return type_(
            [val.as_dict() if hasattr(val, "as_dict") else val for val in value]
        )

    def as_dict(self) -> typing.Dict[str, typing.Any]:
        obj = {"id": self.id}
        for field, value in self.__dict__.items():
            if callable(value):
                continue

            if isinstance(value, Result):
                obj[field] = value.as_dict()
            elif isinstance(value, list):
                obj[field] = self._resolve_list(value, list)
            elif isinstance(value, set):
                obj[field] = self._resolve_list(value, set)
            elif isinstance(value, tuple):
                obj[field] = self._resolve_list(value, tuple)
            else:
                obj[field] = value
        return obj

    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        self.__dict__.update(state)


class EventResult(Result):

    def __init__(
        self,
        error: bool,
        task_id: str,
        event_name: str,
        content: typing.Any,
        init_params: EventResultInitVar = EMPTY,
        call_params: EventResultInitVar = EMPTY,
    ):
        super().__init__(error, content)

        self.task_id: typing.Union[int, str] = task_id
        self.event_name: typing.Union[str, None] = event_name
        self.init_params: EventResultInitVar = init_params
        self.call_params: EventResultInitVar = call_params


class ResultSet(Result, MutableSet):

    def __init__(self, results: typing.List[Result]):
        super().__init__(content={}, error=False)

        for result in results:
            self.content[result.id] = result

    def __contains__(self, item):
        return item.id in self.content

    def __iter__(self):
        for _, result in self.content.items():
            yield result

    def __len__(self):
        return len(self.content)

    def __getitem__(self, index: int):
        return self.content.values()[index]

    def add(self, result: typing.Union[Result, "ResultSet"]):
        if isinstance(result, ResultSet):
            self.content.update(result.content)
        elif isinstance(result, EventResult):
            self.content[result.id] = result

    def clear(self):
        self.content.clear()

    def discard(self, result: typing.Union[EventResult, "ResultSet"]):
        if isinstance(result, ResultSet):
            for res in result:
                self.content.pop(res.id, None)
        else:
            self.content.pop(result.id, None)

    def copy(self):
        new = ResultSet([])
        new.content.update(self.content.copy())
        return new

    def filter(self, **filter_params) -> "ResultSet":

        if "id" in filter_params:
            pk = filter_params["id"]
            try:
                return ResultSet([self.content[pk]])
            except KeyError:
                return ResultSet([])

        def match_conditions(item):
            for key, value in filter_params.items():
                normalized_key = key.replace("_", ".")
                parts = normalized_key.split(".")

                # Traverse nested dictionaries
                current = item
                for part in parts[:-1]:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        break
                else:
                    final_key = parts[-1]
                    if isinstance(current, dict) and final_key in current:
                        current_value = current[final_key]
                        # Special handling for list membership
                        if isinstance(current_value, list):
                            if value not in current_value:
                                return False
                        else:
                            if current_value != value:
                                return False
                    else:
                        return False
            return True

        return ResultSet(list(filter(match_conditions, self.content.values())))

    def first(self):
        try:
            return self[0]
        except IndexError:
            return None

    def __str__(self):
        return str(list(self.content.values()))

    def __repr__(self):
        return "<{}:{}:{}>".format(self.__class__.__name__, self.id, len(self))
