import typing
import warnings
from functools import wraps
from concurrent.futures import Executor
from .base import EventBase
from .utils import EMPTY
from .executors.default_executor import DefaultExecutor


def event(
    executor: typing.Type[Executor] = DefaultExecutor,
    max_workers: typing.Union[int, EMPTY] = EMPTY,
    max_tasks_per_child: typing.Union[int, EMPTY] = EMPTY,
    thread_name_prefix: typing.Union[str, EMPTY] = EMPTY,
    stop_on_exception: bool = False,
):

    def worker(func):
        namespace = {
            "__module__": func.__module__,
            "executor": executor,
            "max_workers": max_workers,
            "max_tasks_per_child": max_tasks_per_child,
            "thread_name_prefix": thread_name_prefix,
            "execution_context": None,
            "previous_result": None,
            "stop_on_exception": stop_on_exception,
            "process": func,
        }

        _event = type(func.__name__, (EventBase,), namespace)
        globals()[func.__name__] = _event

        @wraps(func)
        def task(*args, **kwargs):
            warnings.warn(
                "This is an event that must be executed by an executor", Warning
            )
            return func(*args, **kwargs)

        return task

    return worker
