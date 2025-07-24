import typing
from concurrent.futures import Executor
from event_pipeline.exceptions import ExecutorNotFound


class ExecutorRegistry:
    """Registry for available executors with validation"""

    def __init__(self):
        self._executors: typing.Dict[str, typing.Type[Executor]] = {}

    def register(self, executor_class: typing.Type[Executor]) -> None:
        if not issubclass(executor_class, Executor):
            raise ValueError(f"Invalid executor type: {executor_class}")
        self._executors[executor_class.__name__] = executor_class

    def get(self, name: str) -> typing.Type[Executor]:
        if name not in self._executors:
            raise ExecutorNotFound(f"Executor '{name}' not registered")
        return self._executors[name]
