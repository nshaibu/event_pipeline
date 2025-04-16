from abc import ABC, abstractmethod


class BaseManager(ABC):
    """
    Abstract base class for event managers.
    """

    def __init__(self, host, port):
        self._host = host
        self._port = port

    def __repr__(self):
        return f"{self.__class__.__name__}(host={self._host}, port={self._port})"

    def __str__(self):
        return self.__repr__()

    @abstractmethod
    def start(self, *args, **kwargs):
        """ "Start the task manager server"""

    @abstractmethod
    def shutdown(self):
        """ "Shutdown the task manager server"""

    def __del__(self):
        self.shutdown()
