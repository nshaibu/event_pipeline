import abc
import typing

from .connection import BackendConnectorBase


class KeyValueStoreBackendBase(abc.ABC):
    connector: typing.Type[BackendConnectorBase]

    def __init__(self, **connector_config):
        self.connection = self.connector(**connector_config)

    @abc.abstractmethod
    def set(self, key, value):
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, key):
        raise NotImplementedError

    @abc.abstractmethod
    def exists(self, key):
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, key):
        raise NotImplementedError

    @abc.abstractmethod
    def incr(self, key, amount=1):
        raise NotImplementedError

    @abc.abstractmethod
    def decr(self, key, amount=1):
        raise NotImplementedError

    @abc.abstractmethod
    def lpush(self):
        raise NotImplementedError

    @abc.abstractmethod
    def rpush(self):
        raise NotImplementedError

    @abc.abstractmethod
    def pop(self):
        raise NotImplementedError

    @abc.abstractmethod
    def sadd(self, key, value):
        raise NotImplementedError
