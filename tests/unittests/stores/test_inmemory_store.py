import pytest
from pydantic_mini import BaseModel
from nexus.exceptions import ObjectDoesNotExist
from nexus.backends.stores.inmemory_store import InMemoryKeyValueStoreBackend


class MockModel(BaseModel):
    id: str
    name: str

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getstate__(self):
        return self.__dict__


@pytest.fixture
def store():
    return InMemoryKeyValueStoreBackend()


def test_insert_and_get_record(store):
    schema_name = "test_schema"
    record_key = "1"
    record = MockModel(id="1", name="Test Record")

    store.insert_record(schema_name, record_key, record)
    retrieved_record = store.get_record(schema_name, MockModel, record_key)

    assert retrieved_record == record


def test_exists(store):
    schema_name = "test_schema"
    record_key = "1"
    record = MockModel(id="1", name="Test Record")

    store.insert_record(schema_name, record_key, record)
    assert store.exists(schema_name, record_key) is True
    assert store.exists(schema_name, "nonexistent_key") is False


def test_count(store):
    schema_name = "test_schema"
    record1 = MockModel(id="1", name="Record 1")
    record2 = MockModel(id="2", name="Record 2")

    store.insert_record(schema_name, "1", record1)
    store.insert_record(schema_name, "2", record2)

    assert store.count(schema_name) == 2


def test_delete_record(store):
    schema_name = "test_schema"
    record_key = "1"
    record = MockModel(id="1", name="Test Record")

    store.insert_record(schema_name, record_key, record)
    store.delete_record(schema_name, record_key)

    assert not store.exists(schema_name, record_key)

    with pytest.raises(ObjectDoesNotExist):
        store.delete_record(schema_name, record_key)


def test_update_record(store):
    schema_name = "test_schema"
    record_key = "1"
    record = MockModel(id="1", name="Old Record")
    updated_record = MockModel(id="1", name="Updated Record")

    store.insert_record(schema_name, record_key, record)
    store.update_record(schema_name, record_key, updated_record)

    retrieved_record = store.get_record(schema_name, MockModel, record_key)
    assert retrieved_record == updated_record


def test_reload_record(store):
    schema_name = "test_schema"
    record_key = "1"
    record = MockModel(id="1", name="Test Record")

    store.insert_record(schema_name, record_key, record)
    record.name = "Modified Name"
    store.reload_record(schema_name, record)

    assert record.name == "Modified Name"


def test_filter_record(store):
    schema_name = "test_schema"
    record1 = MockModel(id="1", name="Record 1")
    record2 = MockModel(id="2", name="Record 2")

    store.insert_record(schema_name, "1", record1)
    store.insert_record(schema_name, "2", record2)

    filtered_records = store.filter_record(schema_name, MockModel, id="1")
    assert len(filtered_records) == 1
    assert filtered_records[0] == record1

    filtered_records = store.filter_record(schema_name, MockModel, name="Record 2")
    assert len(filtered_records) == 1
    assert filtered_records[0] == record2

    filtered_records = store.filter_record(schema_name, MockModel, id="3")
    assert len(filtered_records) == 0
