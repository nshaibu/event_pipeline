import typing
from dataclasses import Field, MISSING, asdict, fields
from event_pipeline.mixins.identity import ObjectIdentityMixin
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.exceptions import ValidationError


class QueryManager:

    def __init__(self, schema: 'SchemaMixin'):
        self.schema = schema
        self._cache = {}  # timed cache
        self._length = 0

    def query(self, **kwargs) -> 'QueryResults':
        pass


def validate_type(
    field_name: str, value: typing.Any, expected_type: typing.Any
) -> bool:
    """
    Validates the type of a field based on its annotation.

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
        raise ValueError(
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

    def reload(self):
        self._connector.reload_record(self.get_schema_name(), self)
