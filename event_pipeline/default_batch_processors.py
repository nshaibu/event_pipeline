import typing

DEFAULT_BATCH_SIZE = 100

DEFAULT_CHUNK_SIZE = 4096  # 4K


def list_batch_processor(value: typing.Collection, batch_size: int = DEFAULT_BATCH_SIZE):
    pass


def file_stream_batch_processor(value, chunk_size: int = DEFAULT_CHUNK_SIZE):
    pass
