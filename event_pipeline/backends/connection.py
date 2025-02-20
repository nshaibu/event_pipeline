import logging

from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BackendConnectorBase(ABC):
    """
    Abstract base class for handling backend connections.
    Each subclass will implement connection and query handling
    for a specific backend service.
    """

    def __init__(
        self, host: str, port: int, username: str, password: str, db: str = None
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = db

    @abstractmethod
    def connect(self):
        """Establish the connection to the backend."""
        pass

    @abstractmethod
    def execute_query(self, query: str):
        """Execute a query on the connected backend."""
        pass

    @abstractmethod
    def close(self):
        """Close the connection to the backend."""
        pass
