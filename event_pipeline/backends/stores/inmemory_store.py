import typing
from event_pipeline.exceptions import ObjectDoesNotExist
from event_pipeline.backends.store import KeyValueStoreBackendBase

if typing.TYPE_CHECKING:
    from event_pipeline.mixins.schema import SchemaMixin


class InMemoryKeyValueStoreBackend(KeyValueStoreBackendBase):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._cursor = {}

    def exists(self, schema_name: str, record_key: str) -> bool:
        return schema_name in self._cursor and record_key in self._cursor[schema_name]

    def insert_record(self, schema_name: str, record_key: str, record: "SchemaMixin"):
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
        klass: typing.Type["SchemaMixin"],
        record_key: typing.Union[str, int],
    ):
        try:
            return self._cursor[schema_name][record_key]
        except KeyError:
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

    def update_record(self, schema_name: str, record_key: str, record: "SchemaMixin"):
        if schema_name not in self._cursor:
            self._cursor[schema_name] = {}
        self._cursor[schema_name][record_key] = record

    @staticmethod
    def load_record(record_state, record_klass: typing.Type["SchemaMixin"]):
        record = record_klass.__new__(record_klass)
        record.__setstate__(record_state)
        return record

    def reload_record(self, schema_name: str, record: "SchemaMixin"):
        _record = self.get_record(schema_name, record.__class__, record.id)
        record.__setstate__(_record.__getstate__())
