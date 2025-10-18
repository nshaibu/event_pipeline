import typing
import zlib
import pickle
import cloudpickle
from dataclasses import dataclass


@dataclass
class TaskMessage:
    """Message format for task communication"""

    task_id: str
    fn: typing.Callable
    args: tuple
    kwargs: dict
    client_cert: typing.Optional[bytes] = None
    encrypted: bool = False

    def serialize(self) -> bytes:
        return self.serialize_object(self)

    @staticmethod
    def serialize_object(obj) -> bytes:
        data = cloudpickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        compressed_data = zlib.compress(data)
        return compressed_data

    @staticmethod
    def deserialize(data: bytes) -> typing.Tuple[typing.Any, bool]:
        decompressed_data = zlib.decompress(data)
        decompressed_data = cloudpickle.loads(decompressed_data)
        return decompressed_data, isinstance(decompressed_data, TaskMessage)
