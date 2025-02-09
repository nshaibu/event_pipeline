class ImproperlyConfigured(Exception):
    pass


class PipelineError(Exception):

    def __init__(self, message, code=None, params=None):
        super().__init__(message, code)
        self.message = message
        self.code = code
        self.params = params


class TaskError(PipelineError):
    pass


class EventDoesNotExist(ValueError, PipelineError):
    pass


class StateError(ValueError, PipelineError):
    pass


class EventDone(PipelineError):
    pass


class EventNotConfigured(ImproperlyConfigured):
    pass


class BadPipelineError(ImproperlyConfigured, PipelineError):

    def __init__(self, *args, exception=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = exception


class StopProcessingError(RuntimeError, PipelineError):

    def __init__(self, *args, exception=None, **kwargs):
        self.exception = exception
        super().__init__(*args, **kwargs)
