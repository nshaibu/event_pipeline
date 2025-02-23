import os.path
import typing
from .exceptions import ImproperlyConfigured
from .utils import validate_batch_processor
from .constants import EMPTY, UNKNOWN, BATCH_PROCESSOR_TYPE


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
        batch_processor: BATCH_PROCESSOR_TYPE = None,
        batch_size: int = None,
    ):
        self.name = name
        self.data_type = data_type
        self.default = default
        self.required = required
        self.batch_processor = batch_processor
        self.batch_size: int = batch_size

        if self.batch_processor:
            valid = validate_batch_processor(self.batch_processor)
            if valid is False:
                raise ImproperlyConfigured(
                    "Batch processor error. Batch processor must be iterable and generators"
                )

    def __set_name__(self, owner, name):
        if self.name is None:
            self.name = name

    def __get__(self, instance, owner=None):
        value = instance.__dict__.get(self.name, None)
        if value is None and self.default is not EMPTY:
            return self.default
        return value

    def __set__(self, instance, value):
        if self.data_type and not isinstance(value, self.data_type):
            raise TypeError(
                f"{value} is not in the expected data type. {self.data_type} != {type(value)}."
            )
        if value is None and self.required and self.default is EMPTY:
            raise ValueError(f"Field '{self.name}' is required")
        elif value is None and self.default is not EMPTY:
            value = self.default
        self.set_field_cache_value(instance, value)
        instance.__dict__[self.name] = value

    def get_cache_key(self):
        return self.name

    @property
    def has_batch_operation(self):
        return self.batch_processor is not None


class FileInputDataField(InputDataField):

    def __init__(self, path: str = None, required=False):
        super().__init__(name=path, required=required, data_type=str, default=None)

    def __set__(self, instance, value):
        super().__set__(instance, value)
        if not os.path.isfile(value):
            raise TypeError(f"{value} is not a file or does not exist")

    def __get__(self, instance, owner=None):
        value = super().__get__(instance, owner)
        if value:
            return open(value)
