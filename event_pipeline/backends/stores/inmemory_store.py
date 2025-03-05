import typing
from event_pipeline.exceptions import ObjectDoesNotExist
from event_pipeline.backends.store import KeyValueStoreBackendBase

if typing.TYPE_CHECKING:
    from event_pipeline.mixins.schema import SchemaMixin


class InMemoryKeyValueStoreBackend(KeyValueStoreBackendBase):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._cursor = {}

    def insert_record(self, schema_name: str, record_key: str, record: "SchemaMixin"):
        if schema_name not in self._cursor:
            self._cursor[schema_name] = {}
        self._cursor[schema_name][record_key] = record

    def delete_record(self, schema_name: str, record_key: str):
        del self._cursor[schema_name][record_key]

    def get_record(
        self,
        schema_name: str,
        klass: typing.Type["SchemaMixin"],
        record_key: typing.Union[str, int],
    ):
        try:
            return self._cursor[schema_name][record_key]
        except KeyError:
            raise ObjectDoesNotExist("Record not found")

    def update_record(self, schema_name: str, record_key: str, record: "SchemaMixin"):
        if schema_name not in self._cursor:
            self._cursor[schema_name] = {}
        self._cursor[schema_name][record_key] = record

    @staticmethod
    def load_record(record_state, record_klass: typing.Type["SchemaMixin"]):
        pass
