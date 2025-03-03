import logging
import typing

from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BackendConnectorBase(ABC):
    """
    Abstract base class for handling backend connections.
    Each subclass will implement connection and query handling
    for a specific backend service.
    """

    def __init__(
        self,
        host,
        port,
        username: typing.Any = None,
        password: typing.Any = None,
        db: typing.Any = None,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = db
        self._cursor = None

    @abstractmethod
    def connect(self):
        """Establish the connection to the backend."""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect backend."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @property
    def cursor(self):
        return self._cursor

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
