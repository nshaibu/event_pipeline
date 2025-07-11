import typing


if typing.TYPE_CHECKING:
    from event_pipeline.result import EventResult


class ImproperlyConfigured(Exception):
    pass


class PipelineError(Exception):

    def __init__(self, message, code=None, params=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.params = params

    def to_dict(self):
        return {
            "error_class": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "params": self.params,
        }


class TaskError(PipelineError):
    pass


class EventDoesNotExist(PipelineError, ValueError):
    pass


class StateError(PipelineError, ValueError):
    pass


class EventDone(PipelineError):
    pass


class EventNotConfigured(ImproperlyConfigured):
    pass


class BadPipelineError(ImproperlyConfigured, PipelineError):

    def __init__(self, *args, exception=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = exception


class MultiValueError(PipelineError, KeyError):
    pass


class StopProcessingError(PipelineError, RuntimeError):

    def __init__(self, *args, exception=None, **kwargs):
        self.exception = exception
        super().__init__(*args, **kwargs)


class MaxRetryError(Exception):
    """
    Raised when the maximum number of retries is exceeded.
    """

    def __init__(self, attempt, exception, reason=None):
        self.reason = reason
        self.attempt = attempt
        self.exception = exception
        message = "Max retries exceeded: %s (Caused by %r)" % (
            self.attempt,
            self.reason,
        )
        super().__init__(message)


class ValidationError(PipelineError, ValueError):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class ObjectExistError(ValueError):
    pass


class ObjectDoesNotExist(ValueError):
    """ObjectDoesNotExist raised when an object does not exist."""


class SwitchTask(Exception):

    def __init__(
        self,
        current_task_id: str,
        next_task_descriptor: int,
        result: "EventResult",
        reason="Manual",
    ):
        self.current_task_id = current_task_id
        self.next_task_descriptor = next_task_descriptor
        self.result = result
        self.reason = reason
        self.descriptor_configured: bool = False
        message = "Task switched to %s (Caused by %r)" % (
            self.next_task_descriptor,
            reason,
        )
        super().__init__(message)


class TaskSwitchingError(PipelineError):
    """TaskSwitchingError raised when a task switch fails."""


class SqlOperationError(ValueError):
    """SqlOperationError raised when a SQL operation fails."""


class PipelineExecutionError(PipelineError):
    """Exception raised when pipeline execution fails."""

class PipelineConfigurationError(PipelineError):
    """Exception raised for configuration errors."""
