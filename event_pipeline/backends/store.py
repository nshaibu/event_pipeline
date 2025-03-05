import abc
import typing

from .connection import BackendConnectorBase

if typing.TYPE_CHECKING:
    from event_pipeline.mixins.schema import SchemaMixin


class KeyValueStoreBackendBase(abc.ABC):
    connector_klass: typing.Type[BackendConnectorBase]

    def __init__(self, **connector_config):
        self.connector = self.connector_klass(**connector_config)

    def close(self):
        if self.connector:
            self.connector.disconnect()

    @abc.abstractmethod
    def exists(self, schema_name: str, record_key: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def insert_record(self, schema_name: str, record_key: str, record: "SchemaMixin"):
        raise NotImplementedError

    @abc.abstractmethod
    def update_record(self, schema_name: str, record_key: str, record: "SchemaMixin"):
        raise NotImplementedError

    @abc.abstractmethod
    def delete_record(self, schema_name: str, record_key: str):
        raise NotImplementedError

    @abc.abstractmethod
    def filter_record(self, schema_name: str, record_klass: typing.Type["SchemaMixin"], **filter_kwargs):
        raise NotImplementedError

    @staticmethod
    def load_record(record_state, record_klass: typing.Type["SchemaMixin"]):
        raise NotImplementedError

    @abc.abstractmethod
    def get_record(
        self,
        schema_name: str,
        klass: typing.Type["SchemaMixin"],
        record_key: typing.Union[str, int],
    ):
        raise NotImplementedError

    @abc.abstractmethod
    def reload_record(self, schema_name: str, record: "SchemaMixin"):
        raise NotImplementedError

    @abc.abstractmethod
    def count(self, schema_name: str) -> int:
        raise NotImplementedError
