import typing
from concurrent.futures import Future
from ..base import EventBase, EventResult
from .remote_executor import RemoteExecutor


class RemoteEvent(EventBase):
    """
    Base class for events that will be executed remotely using RemoteExecutor.
    Implements the EventBase interface for remote task execution.
    """

    executor = RemoteExecutor

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._futures: typing.Dict[str, Future] = {}

    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        """
        Process the event remotely using RemoteExecutor.

        Returns:
            Tuple[bool, Any]: A tuple containing:
                - success (bool): Whether the remote execution was successful
                - result (Any): The result of the remote execution
        """
        try:
            # Submit task to remote executor
            future = self.executor.submit(self._execute_remote, *args, **kwargs)

            # Store future for tracking
            task_id = str(id(future))
            self._futures[task_id] = future

            # Get result with timeout
            result = future.result(timeout=self.executor_config.get("timeout", 30))

            if isinstance(result, Exception):
                return False, result

            if isinstance(result, EventResult):
                return not result.error, result.content

            return True, result

        except Exception as e:
            return False, e

    def _execute_remote(self, *args, **kwargs) -> typing.Any:
        """
        This method should be implemented by subclasses to define
        the actual remote task execution logic.
        """
        raise NotImplementedError("Subclasses must implement _execute_remote method")

    def on_success(self, execution_result) -> EventResult:
        """Handle successful remote execution"""
        if isinstance(execution_result, EventResult):
            return execution_result
        return super().on_success(execution_result)

    def on_failure(self, execution_result) -> EventResult:
        """Handle failed remote execution"""
        if isinstance(execution_result, EventResult):
            return execution_result
        return super().on_failure(execution_result)
