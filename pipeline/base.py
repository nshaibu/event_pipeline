import abc
import typing
from enum import Enum


class EventState(Enum):
    INITIALISED = "initialised"
    WAITING = "waiting"


class EventBase(abc.ABC):

    def __init__(self, *args, **kwargs):
        self._status: EventState = EventState.INITIALISED
        self._execution_status: bool = False

    @abc.abstractmethod
    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        pass

    @abc.abstractmethod
    def on_success(self, execution_result):
        # branch to when condition in execution is success
        pass

    @abc.abstractmethod
    def on_failure(self, execution_result):
        # branch to when condition in execution is error
        pass

    @classmethod
    def get_event_klasses(cls):
        for subclass in cls.__subclasses__():
            yield from subclass.get_event_klasses()
            yield subclass

    def __call__(self, *args, **kwargs):
        self._execution_status, execution_result = self.process(*args, **kwargs)
        if self._execution_status:
            return self.on_success(execution_result)
        return self.on_failure(execution_result)
