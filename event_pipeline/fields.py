import os.path
import typing
from .constants import EMPTY, UNKNOWN


class CacheInstanceFieldMixin(object):
    def get_cache_key(self):
        raise NotImplementedError

    def set_field_cache_value(self, instance, value):
        instance._state.set_cache_for_pipeline_field(
            instance, self.get_cache_key(), value
        )


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

    def get_cache_key(self):
        return self.name


class FileInputDataField(InputDataField):

    def __init__(self, path: os.PathLike[str] | str | bytes, required=False):
        super().__init__(
            name=path, required=required, data_type=os.PathLike, default=None
        )

    def __set__(self, instance, value):
        if os.path.isfile(value):
            super().__get__(instance, value)
        else:
            raise TypeError(f"{value} is not a file or does not exist")

    def __get__(self, instance, owner=None):
        if isinstance(self.data_type, os.PathLike):
            return open(self.name, "rwb")
