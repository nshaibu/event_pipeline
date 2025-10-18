import typing
from pydantic_mini import BaseModel
from nexus.exceptions import ObjectDoesNotExist
from nexus.backends.connectors.dummy import DummyConnector
from nexus.backends.store import KeyValueStoreBackendBase


_memory = {}


class InMemoryKeyValueStoreBackend(KeyValueStoreBackendBase):
    connector_klass = DummyConnector

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._cursor = _memory

    def exists(self, schema_name: str, record_key: str) -> bool:
        return schema_name in self._cursor and record_key in self._cursor[schema_name]

    def count(self, schema_name: str) -> int:
        return len(self._cursor[schema_name])

    def insert_record(self, schema_name: str, record_key: str, record: BaseModel):
        if schema_name not in self._cursor:
            self._cursor[schema_name] = {}
        self._cursor[schema_name][record_key] = record

    def delete_record(self, schema_name: str, record_key: str):
        try:
            del self._cursor[schema_name][record_key]
        except KeyError:
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

    def get_record(
        self,
        schema_name: str,
        klass: typing.Type[BaseModel],
        record_key: typing.Union[str, int],
    ):
        try:
            return self._cursor[schema_name][record_key]
        except KeyError:
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

    def update_record(self, schema_name: str, record_key: str, record: BaseModel):
        if schema_name not in self._cursor:
            self._cursor[schema_name] = {}
        self._cursor[schema_name][record_key] = record

    @staticmethod
    def load_record(record_state, record_klass: typing.Type[BaseModel]):
        record = record_klass.__new__(record_klass)
        record.__setstate__(record_state)
        return record

    def reload_record(self, schema_name: str, record: BaseModel):
        _record = self.get_record(schema_name, record.__class__, record.id)
        record.__setstate__(_record.__getstate__())

    def filter_record(
        self,
        schema_name: str,
        record_klass: typing.Type[BaseModel],
        **filter_kwargs,
    ):
        try:
            schema_data = self._cursor[schema_name]
        except KeyError:
            raise ObjectDoesNotExist(f"Schema '{schema_name}' does not exists")

        match_func = self._generate_filter_match(**filter_kwargs)

        if schema_data:
            return [record for record in schema_data.values() if match_func(record)]

        return []
