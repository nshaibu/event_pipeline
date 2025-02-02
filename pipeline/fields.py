import typing
from .constants import EMPTY, UNKNOWN


class CacheInstanceFieldMixin(object):
    def set_field_cache_value(self, instance, value):
        instance._state.set_cache_for_pipeline_field(instance, self.name, value)


class InputDataField(CacheInstanceFieldMixin):

    __slots__ = ("name", "data_type", "default", "required")

    def __init__(
        self,
        name: str = None,
        required: bool = False,
        data_type: typing.Type = UNKNOWN,
        default: typing.Any = EMPTY,
    ):
        self.name = name
        self.data_type = data_type
        self.default = default
        self.required = required

    def __set_name__(self, owner, name):
        if self.name is None:
            self.name = name

    def __get__(self, instance, owner=None):
        value = instance.__dict__.get(self.name, None)
        if value is None:
            return self.default
        return value

    def __set__(self, instance, value):
        if self.data_type and not isinstance(value, self.data_type):
            raise TypeError(
                f"{value} is not in the expected data type. {self.data_type} != {type(value)}."
            )
        self.set_field_cache_value(instance, value)
        instance.__dict__[self.name] = value
