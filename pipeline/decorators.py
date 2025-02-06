from functools import wraps
from .base import EventBase


def event(
    execution_context: "EventExecutionContext",
    previous_result="",
    stop_on_exception: bool = False,
):

    def worker(func):
        namespace = {
            "execution_context": execution_context,
            "previous_result": previous_result,
            "stop_on_exception": stop_on_exception,
            "process": func,
        }

        _event = type(func.__name__, (EventBase,), namespace)

        @wraps(func)
        def task(*args, **kwargs):
            return func(*args, **kwargs)

        setattr(task, "__class__", _event)
        return task

    return worker
