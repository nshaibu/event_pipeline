import os.path
import typing
from . import default_batch_processors as batch_defaults
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
        data_type: typing.Union[typing.Type, typing.Tuple[typing.Type]] = UNKNOWN,
        default: typing.Any = EMPTY,
        batch_processor: BATCH_PROCESSOR_TYPE = None,
        batch_size: int = batch_defaults.DEFAULT_BATCH_SIZE,
    ):
        self.name = name
        self.data_type = (
            data_type if isinstance(data_type, (list, tuple)) else (data_type,)
        )
        self.default = default
        self.required = required
        self.batch_processor = None
        self.batch_size: int = batch_size

        if batch_processor is None:
            if any(
                [
                    dtype.__name__ in [list.__name__, tuple.__name__]
                    for dtype in self.data_type
                    if hasattr(dtype, "__name__")
                ]
            ):
                batch_processor = batch_defaults.list_batch_processor

        if batch_processor:
            self._set_batch_processor(batch_processor)

    def _set_batch_processor(self, processor: BATCH_PROCESSOR_TYPE):
        if processor:
            valid = validate_batch_processor(processor)
            if valid is False:
                raise ImproperlyConfigured(
                    "Batch processor error. Batch processor must be iterable and generators"
                )

            self.batch_processor = processor

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

    def __init__(
        self,
        path: typing.Union[str, os.PathLike] = None,
        required=False,
        chunk_size: int = batch_defaults.DEFAULT_CHUNK_SIZE,
    ):
        super().__init__(
            name=path,
            required=required,
            data_type=(str, os.PathLike),
            default=None,
            batch_size=chunk_size,
            batch_processor=batch_defaults.file_stream_batch_processor,
        )

    def __set__(self, instance, value):
        if not os.path.isfile(value):
            raise TypeError(f"{value} is not a file or does not exist")
        super().__set__(instance, value)

    def __get__(self, instance, owner=None):
        value = super().__get__(instance, owner)
        if value:
            return open(value)
