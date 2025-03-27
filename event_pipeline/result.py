import os
import json
import typing
import pickle
from enum import Enum
from pydantic_mini import BaseModel, MiniAnnotated, Attrib
from datetime import datetime
from collections.abc import MutableSet
from dataclasses import asdict
from .import_utils import import_string
from .exceptions import MultiValueError
from .mixins import ObjectIdentityMixin
from event_pipeline.mixins import BackendIntegrationMixin

__all__ = ["EventResult", "ResultSet"]


class EventResult(BackendIntegrationMixin, BaseModel):
    error: bool
    event_name: str
    content: typing.Any
    task_id: typing.Optional[str]
    init_params: typing.Optional[typing.Dict[str, typing.Any]]
    call_params: typing.Optional[typing.Dict[str, typing.Any]]
    process_id: MiniAnnotated[int, Attrib(default_factory=lambda: os.getpid())]
    creation_time: MiniAnnotated[
        float, Attrib(default_factory=lambda: datetime.now().timestamp())
    ]

    class Config:
        unsafe_hash = False
        frozen = False
        eq = True

    def __hash__(self):
        return hash(self.id)

    def is_error(self) -> bool:
        return self.error

    def as_dict(self):
        return asdict(self)


class Result(ObjectIdentityMixin):

    def __init__(
        self,
        error,
        content: typing.Any,
        content_type: typing.Type = None,
        content_serializer: typing.Callable[[typing.Any], typing.Any] = None,
    ):
        super().__init__()

        self.error: bool = error
        self.process_id = os.getpid()
        self.content: typing.Any = content
        self.content_type: typing.Type = (
            type(content) if content_type is None else content_type
        )
        self._content_serializer: typing.Callable = content_serializer

    def __hash__(self):
        return hash(self.id)

    def is_error(self) -> bool:
        return self.error

    def get_content_type(self) -> typing.Any:
        return self.content_type

    @staticmethod
    def _resolve_list(value: typing.Collection, type_: typing.Type) -> typing.Any:
        return type_(
            [val.as_dict() if hasattr(val, "as_dict") else val for val in value]
        )

    def as_dict(self, ignore_private: bool = True) -> typing.Dict[str, typing.Any]:
        obj = {"id": self.id}
        for field, value in self.__dict__.items():
            if callable(value) or ignore_private and field.startswith("_"):
                continue

            if isinstance(value, Result):
                obj[field] = value.as_dict(ignore_private=ignore_private)
            elif isinstance(value, list):
                obj[field] = self._resolve_list(value, list)
            elif isinstance(value, set):
                obj[field] = self._resolve_list(value, set)
            elif isinstance(value, tuple):
                obj[field] = self._resolve_list(value, tuple)
            else:
                if field == "content":
                    if self._content_serializer and callable(self._content_serializer):
                        obj[field] = self._content_serializer(value)
                    else:
                        obj[field] = value
                else:
                    obj[field] = value
        return obj

    def as_json(self, ignore_private: bool = True) -> str:
        return json.dumps(self.as_dict(ignore_private=ignore_private))

    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        self.__dict__.update(state)


class EntityContentType(BaseModel):
    backend_import_str: str
    entity_content_type: str

    class Config:
        frozen = True
        eq = True

    @classmethod
    def add_entity_content_type(cls, entity: ObjectIdentityMixin):
        if entity and isinstance(entity, ObjectIdentityMixin):
            connector = getattr(entity, "_connector", None)
            if connector:
                backend_import_str = connector.__module__ + "." + connector.__qualname__
            return cls(
                backend_import_str=backend_import_str,
                entity_content_type=entity.__object_import_str__,
            )

    def get_backend(self):
        return import_string(self.backend_import_str)

    def get_content_type(self):
        return import_string(self.entity_content_type)

    def as_dict(self):
        return asdict(self)


class ResultSet(Result, MutableSet):
    _context_types: typing.Set[EntityContentType] = set()

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
        return list(self.content.values())[index]

    def _insert_entity(self, record: ObjectIdentityMixin):
        self.content[record.id] = record
        content_type = EntityContentType.add_entity_content_type(record)
        if content_type and content_type not in self._context_types:
            self._context_types.add(content_type)

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

    def get(self, **filters: typing.Any) -> Result:
        qs = self.filter(**filters)
        if len(qs) > 1:
            raise MultiValueError("More than one result found. {}!=1".format(len(qs)))
        return qs[0]

    def filter(self, **filter_params) -> "ResultSet":
        if "id" in filter_params:
            pk = filter_params["id"]
            try:
                return ResultSet([self.content[pk]])
            except KeyError:
                return ResultSet([])

        def match_conditions(result):
            # TODO: implement filter for nested dict and list
            return all(
                [
                    getattr(result, key, None) == value
                    for key, value in filter_params.items()
                    if hasattr(result, key)
                ]
            )

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
