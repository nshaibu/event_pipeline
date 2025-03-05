import abc
import typing

from .connection import BackendConnectorBase


class KeyValueStoreBackendBase(abc.ABC):
    connector_klass: typing.Type[BackendConnectorBase]

    def __init__(self, **connector_config):
        self.connector = self.connector_klass(**connector_config)

    def close(self):
        if self.connector:
            self.connector.disconnect()

    @abc.abstractmethod
    def insert_record(self, schema_name: str, record_key: str, record):
        raise NotImplementedError

    @abc.abstractmethod
    def update_record(self, schema_name: str, record_key: str, record: typing.Dict):
        raise NotImplementedError

    @abc.abstractmethod
    def delete_record(self, schema_name: str, record_key: str):
        raise NotImplementedError
