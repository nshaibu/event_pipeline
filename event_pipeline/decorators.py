import typing
import warnings
from functools import wraps
from concurrent.futures import Executor
from .base import EventBase
from .utils import EMPTY
from .executors.default_executor import DefaultExecutor


def event(
    executor: typing.Type[Executor] = DefaultExecutor,
    # max_workers: typing.Union[int, EMPTY] = EMPTY,
    # max_tasks_per_child: typing.Union[int, EMPTY] = EMPTY,
    # thread_name_prefix: typing.Union[str, EMPTY] = EMPTY,
    stop_on_exception: bool = False,
):

    def worker(func):
        namespace = {
            "__module__": func.__module__,
            "executor": executor,
            # "max_workers": max_workers,
            # "max_tasks_per_child": max_tasks_per_child,
            # "thread_name_prefix": thread_name_prefix,
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


def listener(signal, **kwargs):
    """
    A decorator to connect a callback function to a specified signal or signals.

    This function allows you to easily connect a callback to one or more signals, enabling
    it to be invoked when the signal is emitted.

    Usage:

        @listener(task_submit, sender=MyModel)
        def callback(sender, **kwargs):
            # This callback will be executed when the post_save signal is emitted
            ...

        @listener([task_submit, pipeline_init], sender=MyModel)
        def callback(sender, **kwargs):
            # This callback will be executed for both post_save and post_delete signals
            pass

    Args:
        signal (Union[Signal, List[Signal]]): A single signal or a list of signals to which the
                                               callback function will be connected.
        **kwargs: Additional keyword arguments that can be passed to the signal's connect method.

    Returns:
        function: The original callback function wrapped with the connection logic.
    """

    def wrapper(func):
        if isinstance(signal, (list, tuple)):
            for s in signal:
                s.connect(listener=func, **kwargs)
        else:
            signal.connect(listener=func, **kwargs)
        return func

    return wrapper
