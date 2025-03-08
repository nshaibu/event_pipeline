import typing
from datetime import datetime
from dataclasses import Field, fields, is_dataclass
from event_pipeline.mixins.identity import ObjectIdentityMixin
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.exceptions import ValidationError
from event_pipeline.typing import (
    PipelineAnnotated,
    Query,
    is_pipeline_annotated,
    get_type,
)
from event_pipeline.backends.stores.inmemory_store import InMemoryKeyValueStoreBackend


class SchemaMixin(ObjectIdentityMixin):
    backend: typing.Type[KeyValueStoreBackendBase] = InMemoryKeyValueStoreBackend

    _connector: KeyValueStoreBackendBase = None

    def __post_init__(self):
        """
        The validation is performed by calling a function named:
            `validate_<field_name>(self, value, field) -> field.type`
        """
        super().__init__()

        for fd in fields(self):
            self._field_type_validator(fd)

            method = getattr(self, f"validate_{fd.name}", None)
            if method and callable(method):
                setattr(self, fd.name, method(getattr(self, fd.name), field=fd))

    def _field_type_validator(self, fd: Field):
        value = getattr(self, fd.name, None)
        field_type = fd.type

        if not is_pipeline_annotated(field_type):
            raise ValidationError(
                "Field '{}' should be annotated with 'PipelineAnnotated'.".format(
                    fd.name
                ),
                params={"field": fd.name, "annotation": field_type},
            )

        if not field_type.has_default() and value is None:
            raise ValidationError(
                "Field '{}' should not be empty.".format(fd.name),
                params={"field": fd.name, "annotation": field_type},
            )

        expected_type = (
            hasattr(field_type, "__args__") and field_type.__args__[0] or None
        )
        expected_type = (
            expected_type and self.type_can_be_validated(expected_type) or None
        )

        if expected_type and expected_type is not typing.Any:
            if not isinstance(value, expected_type):
                raise TypeError(
                    f"Field '{fd.name}' should be of type {expected_type.__name__}, "
                    f"but got {type(value).__name__}."
                )

    @staticmethod
    def type_can_be_validated(typ) -> typing.Optional[typing.Tuple]:
        origin = typing.get_origin(typ)
        if origin is typing.Union:
            type_args = typing.get_args(typ)
            if type_args:
                return tuple([get_type(_type) for _type in type_args])
        else:
            return (get_type(typ),)

    def get_schema_name(self) -> str:
        return self.__class__.__name__

    def __getstate__(self):
        state = {}
        for name, _ in fields(self):
            state[name] = getattr(self, name, None)
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def _connect(self, **kwargs):
        if self._connector is None:
            self._connector = self.backend(**kwargs)
        return self._connector

    def _disconnect(self):
        if self._connector is not None:
            self._connector.close()

    def save(self):
        self._connector.insert_record(
            schema_name=self.get_schema_name(), record_key=self.id, record=self
        )

    def reload(self):
        self._connector.reload_record(self.get_schema_name(), self)

    def delete(self):
        self._connector.delete_record(
            schema_name=self.get_schema_name(), record_key=self.id
        )

    def update(self):
        self._connector.update_record(
            schema_name=self.get_schema_name(), record_key=self.id, record=self
        )
