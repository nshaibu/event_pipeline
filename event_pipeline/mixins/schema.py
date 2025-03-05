import typing
from threading import Lock
from collections.abc import MutableSet
from dataclasses import Field, MISSING, asdict, fields
from event_pipeline.mixins.identity import ObjectIdentityMixin
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.exceptions import ValidationError


class ResultSet(MutableSet):

    def __init__(self, manager):
        self._manager = manager

    def __contains__(self, item):
        return item.id in self.content

    def __iter__(self):
        for _, result in self.content.items():
            yield result

    def __len__(self):
        return len(self.content)

    def __getitem__(self, index: int):
        return list(self.content.values())[index]

    def add(self, record: "SchemaMixin"):
        record.save()

    def clear(self):
        self.content.clear()

    # def discard(self, result: typing.Union[EventResult, "ResultSet"]):
    #     if isinstance(result, ResultSet):
    #         for res in result:
    #             self.content.pop(res.id, None)
    #     else:
    #         self.content.pop(result.id, None)
    #
    # def copy(self):
    #     new = ResultSet([])
    #     new.content.update(self.content.copy())
    #     return new
    #
    # def get(self, **filters: typing.Any) -> Result:
    #     qs = self.filter(**filters)
    #     if len(qs) > 1:
    #         raise MultiValueError("More than one result found. {}!=1".format(len(qs)))
    #     return qs[0]
    #
    # def filter(self, **filter_params) -> "ResultSet":
    #     if "id" in filter_params:
    #         pk = filter_params["id"]
    #         try:
    #             return ResultSet([self.content[pk]])
    #         except KeyError:
    #             return ResultSet([])
    #
    #     def match_conditions(result):
    #         # TODO: implement filter for nested dict and list
    #         return all(
    #             [
    #                 getattr(result, key, None) == value
    #                 for key, value in filter_params.items()
    #                 if hasattr(result, key)
    #             ]
    #         )
    #
    #     return ResultSet(list(filter(match_conditions, self.content.values())))
    #
    # def first(self):
    #     try:
    #         return self[0]
    #     except IndexError:
    #         return None
    #
    # def __str__(self):
    #     return str(list(self.content.values()))
    #
    # def __repr__(self):
    #     return "<{}:{}:{}>".format(self.__class__.__name__, self.id, len(self))


class QueryManager:

    def __init__(self, schema: "SchemaMixin"):
        self.schema = schema
        self._cache = {}  # timed cache
        self._length = 0
        self._modified = False
        self._lock = Lock()

    def query(self, **filter_kwargs) -> ResultSet:
        pass


def validate_type(
    field_name: str, value: typing.Any, expected_type: typing.Any
) -> bool:
    """
    Validates the type of field based on its annotation.

    Args:
        field_name (str): Name of the field.
        value (Any): Value of the field to validate.
        expected_type (Any): Expected type of the field.

    Returns:
        bool: True if the value matches the expected type, False otherwise.

    Raises:
        TypeError: If the type does not match the expected type.
    """
    is_optional = hasattr(expected_type, "__origin__") and expected_type.__origin__ in {
        typing.Union,
        typing.Optional,
    }

    # If the field is not optional and is None, raise an error
    if not is_optional and value is None:
        raise ValidationError(
            f"Field '{field_name}' is required but not provided (value is None)."
        )

    if isinstance(expected_type, type):
        # Direct type comparison (e.g., int, str, etc.)
        if not isinstance(value, expected_type):
            raise TypeError(
                f"Field '{field_name}' should be of type {expected_type.__name__}, "
                f"but got {type(value).__name__}."
            )

    elif hasattr(
        expected_type, "__origin__"
    ):  # For generic types like Optional, List, etc.
        origin = expected_type.__origin__

        if origin is typing.Union:
            # Check if the value matches any of the types in the Union
            if not any(isinstance(value, t) for t in expected_type.__args__):
                raise TypeError(
                    f"Field '{field_name}' value {value} does not match any type in {expected_type}."
                )

        elif origin is typing.Optional:
            # Optional is just Union with NoneType
            if value is not None and not isinstance(value, expected_type.__args__[0]):
                raise TypeError(
                    f"Field '{field_name}' should be of type {expected_type.__args__[0].__name__} or None."
                )

        elif origin is list:
            # If the field is a list, check if the items inside are of the correct type
            item_type = expected_type.__args__[0]
            if not all(isinstance(item, item_type) for item in value):
                raise TypeError(
                    f"Field '{field_name}' should be a list of {item_type.__name__}, "
                    f"but found items of type {type(value[0]).__name__}."
                )

    return True


class SchemaMixin(ObjectIdentityMixin):
    backend: typing.Type[KeyValueStoreBackendBase]

    _connector: KeyValueStoreBackendBase = None

    def __post_init__(self):
        """
        The validation is performed by calling a function named:
            `validate_<field_name>(self, value, field) -> field.type`
        """
        super().__init__()

        self.manager = QueryManager(self)

        for field in fields(self):
            self._field_type_validator(field)

            method = getattr(self, f"validate_{field.name}", None)
            if method and callable(method):
                setattr(
                    self, field.name, method(getattr(self, field.name), field=field)
                )

    def _field_type_validator(self, field: Field):
        value = getattr(self, field.name)
        if field.default is None and value is None:
            raise ValidationError(f"Field {field.name} is required")
        expected_type = field.type
        validate_type(field.name, getattr(self, field.name), expected_type)

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
        self.manager._modified = True

    def reload(self):
        self._connector.reload_record(self.get_schema_name(), self)
