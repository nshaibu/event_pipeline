import typing
import warnings
from functools import wraps
from concurrent.futures import Executor
from .base import EventBase, RetryPolicy, ExecutorInitializerConfig
from .executors.default_executor import DefaultExecutor


def event(
    executor: typing.Type[Executor] = DefaultExecutor,
    retry_policy: typing.Union[RetryPolicy, typing.Dict[str, typing.Any]] = None,
    executor_config: typing.Union[
        ExecutorInitializerConfig, typing.Dict[str, typing.Any]
    ] = None,
):

    def worker(func):

        @wraps(func)
        def inner(self, *args, **kwargs):
            event_ref = self
            return func(*args, **kwargs)

        namespace = {
            "__module__": func.__module__,
            "executor": executor,
            "retry_policy": retry_policy,
            "executor_config": executor_config,
            "execution_context": None,
            "previous_result": None,
            "stop_on_exception": False,
            "process": inner,
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


def listener(signal, sender):
    """
    A decorator to connect a callback function to a specified signal or signals.

    This function allows you to easily connect a callback to one or more signals, enabling
    it to be invoked when the signal is emitted.

    Usage:

        @listener(task_submit, sender=MyModel)
        def callback(sender, signal, **kwargs):
            # This callback will be executed when the post_save signal is emitted
            ...

        @listener([task_submit, pipeline_init], sender=MyModel)
        def callback(sender, signal, **kwargs):
            # This callback will be executed for both post_save and post_delete signals
            pass

    Args:
        signal (Union[Signal, List[Signal]]): A single signal or a list of signals to which the
                                               callback function will be connected.
        sender: Additional keyword arguments that can be passed to the signal's connect method.

    Returns:
        function: The original callback function wrapped with the connection logic.
    """

    def wrapper(func):
        if isinstance(signal, (list, tuple)):
            for s in signal:
                s.connect(listener=func, sender=sender)
        else:
            signal.connect(listener=func, sender=sender)
        return func

    return wrapper
