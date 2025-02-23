import typing
from io import IOBase
from more_itertools import batched

DEFAULT_BATCH_SIZE = 100

DEFAULT_CHUNK_SIZE = 10240  # 10K


def list_batch_processor(
    values: typing.Collection, batch_size: int = DEFAULT_BATCH_SIZE
):
    yield from batched(values, batch_size)


def file_stream_batch_processor(values: IOBase, chunk_size: int = DEFAULT_CHUNK_SIZE):
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
