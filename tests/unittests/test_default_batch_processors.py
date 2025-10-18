import pytest
from io import StringIO

from nexus.default_batch_processors import (
    list_batch_processor,
    file_stream_batch_processor,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHUNK_SIZE,
)


def test_list_batch_processor():
    values = list(range(10))
    batch_size = 3
    result = list(list_batch_processor(values, batch_size))
    assert result == [(0, 1, 2), (3, 4, 5), (6, 7, 8), (9,)]

    # Test with default batch size
    result = list(list_batch_processor(values))
    assert result == [tuple(values)]  # Since default batch size is larger than the list


def test_file_stream_batch_processor():
    data = "abcdefghijklmnopqrstuvwxyz"
    stream = StringIO(data)

    # Test with default chunk size
    result = list(file_stream_batch_processor(stream))
    assert result == [data]  # Default chunk size is larger than the data

    # Test with custom chunk size
    chunk_size = 5
    stream.seek(0)  # Reset stream position
    result = list(file_stream_batch_processor(stream, chunk_size))
    assert result == ["abcde", "fghij", "klmno", "pqrst", "uvwxy", "z"]

    # Test with non-readable stream
    class NonReadableStream(StringIO):
        def readable(self):
            return False

    non_readable_stream = NonReadableStream(data)
    with pytest.raises(ValueError, match="is not a readable stream"):
        list(file_stream_batch_processor(non_readable_stream))

    # Test with invalid input
    with pytest.raises(ValueError, match="is not a file stream"):
        list(file_stream_batch_processor("not a stream"))
