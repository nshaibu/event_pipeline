import pytest
import zlib
import cloudpickle
from event_pipeline.executors.message import TaskMessage


def test_task_message_serialization_and_deserialization():
    # Create a sample TaskMessage object
    task_message = TaskMessage(
        task_id="123",
        fn=lambda x: x + 1,
        args=(1,),
        kwargs={"key": "value"},
        client_cert=b"sample_cert",
        encrypted=True,
    )

    # Serialize the TaskMessage object
    serialized_data = task_message.serialize()
    assert isinstance(serialized_data, bytes)

    # Deserialize the serialized data
    deserialized_data, is_task_message = TaskMessage.deserialize(serialized_data)
    assert is_task_message
    assert isinstance(deserialized_data, TaskMessage)

    # Verify the deserialized object matches the original
    assert deserialized_data.task_id == task_message.task_id
    assert deserialized_data.encrypted == task_message.encrypted
    assert deserialized_data.client_cert == task_message.client_cert
    assert deserialized_data.args == task_message.args
    assert deserialized_data.kwargs == task_message.kwargs
    assert deserialized_data.fn(1) == task_message.fn(1)


def test_serialize_object_static_method():
    # Test serialization of a generic object
    obj = {"key": "value"}
    serialized_data = TaskMessage.serialize_object(obj)
    assert isinstance(serialized_data, bytes)

    # Decompress and deserialize the data to verify correctness
    decompressed_data = zlib.decompress(serialized_data)
    deserialized_obj = cloudpickle.loads(decompressed_data)
    assert deserialized_obj == obj


def test_deserialize_static_method_with_invalid_data():
    # Test deserialization with invalid data
    invalid_data = b"not a valid serialized object"
    with pytest.raises(zlib.error):
        TaskMessage.deserialize(invalid_data)
