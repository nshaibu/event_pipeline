class PipelineError(Exception):

    def __init__(self, message, code=None):
        self.code = code
        super().__init__(message)


class TaskError(PipelineError):
    pass


class EventDoesNotExist(ValueError, PipelineError):
    pass


class EventDone(PipelineError):
    pass


class EventNotConfigured(Exception):
    pass
