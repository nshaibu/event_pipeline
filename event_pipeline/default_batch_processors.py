import typing
from io import IOBase
from more_itertools import batched

DEFAULT_BATCH_SIZE = 100

DEFAULT_CHUNK_SIZE = 10240  # 10K


def list_batch_processor(
    values: typing.Collection, batch_size: int = DEFAULT_BATCH_SIZE
):
    """
    Yields items from a collection in batches of a specified size.

    This is useful for processing large lists or collections in smaller, more manageable chunks.

    Args:
        values (Collection): The input collection to be processed in batches.
        batch_size (int): The number of items per batch. Defaults to DEFAULT_BATCH_SIZE.

    Yields:
        Sequence: A batch (subset) of items from the original collection.
    """
    yield from batched(values, batch_size)


def file_stream_batch_processor(values: IOBase, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """
    Reads a file-like stream in fixed-size chunks and yields each chunk as a generator.

    This is useful for processing large files or data streams in memory-efficient batches.

    Args:
        values (IOBase): A readable file-like object (e.g., open file, BytesIO, etc.).
        chunk_size (int): The number of bytes to read at a time. Defaults to DEFAULT_CHUNK_SIZE.

    Yields:
        bytes: A chunk of data read from the stream.

    Raises:
        ValueError: If the provided object is not a readable stream.
    """
    if isinstance(values, IOBase):
        if not values.readable():
            raise ValueError(f"'{values}' is not a readable stream")
        values.seek(0, 0)
        while True:
            chunk = values.read(chunk_size)
            if not chunk:
                break
            yield chunk
    else:
        raise ValueError(f"'{values}' is not a file stream")
