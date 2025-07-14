import os
import typing
from pydantic_mini.typing import is_type
from . import default_batch_processors as batch_defaults
from .exceptions import ImproperlyConfigured
from .utils import validate_batch_processor
from .constants import EMPTY, UNKNOWN, BATCH_PROCESSOR_TYPE

T = typing.TypeVar("T")


class FileProxy:
    """
    A proxy class that implements the file protocol and manages file lifecycle.

    This class lazily opens files when needed and ensures they are properly closed
    when the proxy is garbage collected or explicitly closed.
    """

    def __init__(
        self,
        file_path: typing.Union[str, os.PathLike],
        mode: str = "r",
        buffering: int = -1,
        encoding: typing.Optional[str] = None,
        errors: typing.Optional[str] = None,
        newline: typing.Optional[str] = None,
        closefd: bool = True,
        opener: typing.Optional[typing.Callable] = None,
    ):
        """
        Initialize the FileProxy with the path and parameters for opening the file.

        Args:
            file_path: Path to the file
            mode: File opening mode ('r', 'w', 'rb', etc.)
            buffering: Buffering policy (-1 for default, 0 for off, 1 for line, >1 for size)
            encoding: Text encoding to use (for text mode)
            errors: Error handling strategy for encoding/decoding errors
            newline: Newline character handling
            closefd: Whether to close the file descriptor when closing the file
            opener: Custom opener function
        """
        self.file_path = file_path
        self.mode = mode
        self.buffering = buffering
        self.encoding = encoding
        self.errors = errors
        self.newline = newline
        self.closefd = closefd
        self.opener = opener

        # File handle is None until first use
        self._file: typing.Optional[typing.IO] = None
        self._closed = False

    def __repr__(self) -> str:
        """Return string representation of the FileProxy."""
        status = "closed" if self.closed else "open" if self._file else "unopened"
        return f"<FileProxy {self.file_path} ({status})>"

    def _ensure_open(self) -> typing.IO:
        """
        Ensure the file is open, opening it if necessary.

        Returns:
            The open file object

        Raises:
            ValueError: If the file is already closed
        """
        if self._closed:
            raise ValueError("I/O operation on closed file")

        if self._file is None:
            self._file = open(
                self.file_path,
                mode=self.mode,
                buffering=self.buffering,
                encoding=self.encoding,
                errors=self.errors,
                newline=self.newline,
                closefd=self.closefd,
                opener=self.opener,
            )

        return self._file

    @property
    def closed(self) -> bool:
        return self._closed or (self._file is not None and self._file.closed)

    def close(self) -> None:
        if self._file is not None and not self._file.closed:
            self._file.close()
        self._closed = True
        self._file = None

    def __enter__(self) -> "FileProxy":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures file is closed."""
        self.close()

    def __del__(self) -> None:
        """Destructor - ensures file is closed when object is garbage collected."""
        self.close()

    # File object methods
    def read(self, size: typing.Optional[int] = None) -> typing.AnyStr:
        """
        Read at most size bytes from the file.

        Args:
            size: Maximum number of bytes/chars to read

        Returns:
            The read content
        """
        return (
            self._ensure_open().read(size)
            if size is not None
            else self._ensure_open().read()
        )

    def readline(self, size: int = -1) -> typing.AnyStr:
        return self._ensure_open().readline(size)

    def readlines(self, hint: int = -1) -> typing.List[typing.AnyStr]:
        return self._ensure_open().readlines(hint)

    def write(self, s: typing.AnyStr) -> int:
        return self._ensure_open().write(s)

    def writelines(self, lines: typing.List[typing.AnyStr]) -> None:
        self._ensure_open().writelines(lines)

    def flush(self) -> None:
        if self._file is not None:
            self._file.flush()

    def seek(self, offset: int, whence: int = 0) -> int:
        """
        Set the current file position.

        Args:
            offset: Offset relative to position indicated by whence
            whence: 0 for beginning, 1 for current position, 2 for end

        Returns:
            The new position
        """
        return self._ensure_open().seek(offset, whence)

    def tell(self) -> int:
        return self._ensure_open().tell()

    def truncate(self, size: typing.Optional[int] = None) -> int:
        return self._ensure_open().truncate(size)

    def fileno(self) -> int:
        return self._ensure_open().fileno()

    def isatty(self) -> bool:
        return self._ensure_open().isatty()

    @property
    def name(self) -> str:
        return str(self.file_path)

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        self._mode = value

    def readable(self) -> bool:
        return "r" in self.mode or "+" in self.mode

    def writable(self) -> bool:
        return "w" in self.mode or "a" in self.mode or "+" in self.mode

    def seekable(self) -> bool:
        if self._file is not None:
            return self._file.seekable()
        # Most files are seekable, but we can't know for sure until opened
        return True

    # Iterator protocol
    def __iter__(self) -> typing.Iterator[typing.AnyStr]:
        """Return self as an iterator."""
        return self

    def __next__(self) -> typing.AnyStr:
        """Return the next line or raise StopIteration."""
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    # Context manager for specific operations
    def open_for_operation(self, func: typing.Callable[[typing.IO], T]) -> T:
        """
        Open the file, perform an operation, and ensure it's closed afterward.

        Args:
            func: Function that takes an open file object and returns a result

        Returns:
            The result of the function
        """
        file = self._ensure_open()
        try:
            return func(file)
        finally:
            # We don't close here as FileProxy manages the lifecycle
            pass


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
        default_factory: typing.Callable[[], typing.Any] = None,
        batch_processor: BATCH_PROCESSOR_TYPE = None,
        batch_size: int = batch_defaults.DEFAULT_BATCH_SIZE,
        help_text: str = None,
    ):
        self.name = name
        self.data_type = (
            data_type if isinstance(data_type, (list, tuple)) else (data_type,)
        )

        for _type in self.data_type:
            if _type is not UNKNOWN and not is_type(_type):
                raise TypeError(f"Data type '{_type}' is not valid type")

        self.default = default
        self.default_factory = default_factory
        self.required = required
        self.batch_processor = None
        self.batch_size: int = batch_size
        self.help_text = help_text

        # Auto-set batch processor for list/tuple types if none provided
        if batch_processor is None:
            if any(
                [
                    getattr(dtype, "__name__", None) in ["list", "tuple"]
                    for dtype in self.data_type
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
        """
        Set the name of this field when it's assigned to a class.

        Args:
            owner: The class owning this field
            name: The name this field is assigned to
        """
        if self.name is None:
            self.name = name

    def __get__(self, instance, owner=None):
        """
        Get the value of this field from an instance.

        Args:
            instance: The instance to get the value from
            owner: The class owning this field

        Returns:
            The field value or default
        """
        if instance is None:
            return self

        value = instance.__dict__.get(self.name, None)
        if value is None:
            if self.default is not EMPTY:
                return self.default
            elif self.default_factory is not None:
                return self.default_factory()

        return value

    def __set__(self, instance, value):
        """
        Set the value of this field on an instance.

        Args:
            instance: The instance to set the value on
            value: The value to set

        Raises:
            TypeError: If the value is not of the expected type
            ValueError: If the field is required but no value is provided
        """
        if UNKNOWN not in self.data_type and value is not None:
            if not isinstance(value, self.data_type):
                raise TypeError(
                    f"Value for '{self.name}' has incorrect type. Expected {self.data_type}, "
                    f"got {type(value).__name__}."
                )

        if value is None:
            if self.required and self.default is EMPTY and self.default_factory is None:
                raise ValueError(f"Field '{self.name}' is required")
            elif self.default is not EMPTY:
                value = self.default
            elif self.default_factory is not None:
                value = self.default_factory()

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
        required: bool = False,
        chunk_size: int = batch_defaults.DEFAULT_CHUNK_SIZE,
        mode: str = "r",
        encoding: typing.Optional[str] = None,
        help_text: str = None,
    ):
        self.mode = mode
        self.encoding = encoding

        super().__init__(
            name=path,
            required=required,
            data_type=(str, os.PathLike),
            default=EMPTY,
            batch_size=chunk_size,
            batch_processor=batch_defaults.file_stream_batch_processor,
            help_text=help_text,
        )

    def __set__(self, instance, value):
        """
        Set the file path, validating that it exists and is a file.

        Args:
            instance: The instance to set the value on
            value: The file path

        Raises:
            ValueError: If the path doesn't exist or is not a file
        """
        if value is not None and not os.path.isfile(value):
            raise ValueError(f"Path '{value}' is not a file or does not exist")

        super().__set__(instance, value)

    def __get__(self, instance, owner=None) -> typing.Optional[FileProxy]:
        """
        Get an open file handle for the file path.

        Args:
            instance: The instance to get the value from
            owner: The class that owns this descriptor

        Returns:
            An open file object or None if no path is set

        Note:
            The caller is responsible for closing the file when done
        """
        if instance is None:
            return self

        value: typing.Union[str, os.PathLike] = super().__get__(instance, owner)

        if value:
            kwargs = {}
            if "b" not in self.mode and self.encoding is not None:
                kwargs["encoding"] = self.encoding

            return FileProxy(file_path=value, mode=self.mode, **kwargs)

        return None
