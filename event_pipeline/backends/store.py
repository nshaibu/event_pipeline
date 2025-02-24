import abc
from .connection import BackendConnectorBase


class KeyValueStoreBackendBase(abc.ABC):
    connector: BackendConnectorBase = None

    @abc.abstractmethod
    def set(self, key, value):
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, key):
        raise NotImplementedError

    @abc.abstractmethod
    def exists(self, key):
        raise NotImplementedError
