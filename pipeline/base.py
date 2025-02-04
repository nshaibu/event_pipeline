import abc
import typing
import logging
from enum import Enum
from concurrent.futures import Executor


logger = logging.getLogger(__name__)


class EventState(Enum):
    INITIALISED = "initialised"
    WAITING = "waiting"


class EventBase(abc.ABC):
    executor: typing.Type[Executor]

    def __init__(self, *args, **kwargs):
        self._status: EventState = EventState.INITIALISED
        self._execution_context: "EventExecutionContext" = kwargs.pop(
            "execution_context"
        )

    @classmethod
    def get_executor_class(cls) -> typing.Type[Executor]:
        return cls.executor

    @abc.abstractmethod
    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        raise NotImplementedError

    @abc.abstractmethod
    def on_success(self, execution_result) -> typing.Dict[typing.Any, typing.Any]:
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
        try:
            self._execution_status, execution_result = self.process(*args, **kwargs)
        except Exception as e:
            logger.exception(str(e), exc_info=e)
            return self.on_failure(e)
        if self._execution_status:
            return self.on_success(execution_result)
        return self.on_failure(execution_result)
