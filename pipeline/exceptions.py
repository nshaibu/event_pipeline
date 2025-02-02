class ImproperlyConfigured(Exception):
    pass


class PipelineError(Exception):

    def __init__(self, message, code=None, params=None):
        super().__init__(message, code, params)
        if isinstance(message, PipelineError):
            if hasattr(message, "error_dict"):
                message = message.error_dict
            elif not hasattr(message, "message"):
                message = message.error_list
            else:
                message, code, params = message.message, message.code, message.params

        if isinstance(message, dict):
            self.error_dict = {}
            for field, messages in message.items():
                if not isinstance(messages, PipelineError):
                    messages = PipelineError(messages)
                self.error_dict[field] = messages.error_list

        elif isinstance(message, list):
            self.error_list = []
            for message in message:
                if not isinstance(message, PipelineError):
                    message = PipelineError(message)
                if hasattr(message, "error_dict"):
                    self.error_list.extend(sum(message.error_dict.values(), []))
                else:
                    self.error_list.extend(message.error_list)
        else:
            self.message = message
            self.code = code
            self.params = params
            self.error_list = [self]

    @property
    def message_dict(self):
        # Trigger an AttributeError if this ValidationError
        # doesn't have an error_dict.
        getattr(self, "error_dict")

        return dict(self)

    @property
    def messages(self):
        if hasattr(self, "error_dict"):
            return sum(dict(self).values(), [])
        return list(self)

    def __iter__(self):
        if hasattr(self, "error_dict"):
            for field, errors in self.error_dict.items():
                yield field, list(PipelineError(errors))
        else:
            for error in self.error_list:
                message = error.message
                if error.params:
                    message %= error.params
                yield str(message)

    def __str__(self):
        if hasattr(self, "error_dict"):
            return repr(dict(self))
        return repr(list(self))


class TaskError(PipelineError):
    pass


class EventDoesNotExist(ValueError, PipelineError):
    pass


class EventDone(PipelineError):
    pass


class EventNotConfigured(ImproperlyConfigured):
    pass


class BadPipelineError(ImproperlyConfigured, PipelineError):

    def __init__(self, *args, exception=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = exception
