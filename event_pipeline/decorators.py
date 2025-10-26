import typing
from concurrent.futures import Executor
from .base import EventBase, RetryPolicy, ExecutorInitializerConfig
from .executors.default_executor import DefaultExecutor

if typing.TYPE_CHECKING:
    from .signal import SoftSignal


# Type definitions
F = typing.TypeVar("F", bound=typing.Callable[..., typing.Any])
T = typing.TypeVar("T")


def event(
    name: typing.Optional[str] = None,
    executor: typing.Optional[typing.Type[Executor]] = None,
    retry_policy: typing.Optional[RetryPolicy] = None,
    executor_config: typing.Optional[ExecutorInitializerConfig] = None,
) -> typing.Callable[[F], typing.Type[EventBase]]:
    """
    Decorator to create an Event class from a function.

    Args:
        executor: Executor class to use (defaults to DefaultExecutor)
        retry_policy: Retry configuration
        executor_config: Executor configuration
        name: Custom name for the event (defaults to function name)

    Returns:
        Event class that can be instantiated and executed

    Example:
        @event(retry_policy=RetryPolicy(max_attempts=5))
        def process_data(data: dict) -> typing.Tuple[bool, typing.Any]:
            # Process the data
            return True, "processed"
    """

    def decorator(func: F) -> typing.Type[EventBase]:
        event_name = name or func.__name__
        executor_class = executor or DefaultExecutor
        _retry_policy = retry_policy or RetryPolicy
        _executor_config = executor_config or ExecutorInitializerConfig()

        class GeneratedEvent(EventBase):
            """Dynamically generated event class."""

            executor = executor_class
            executor_config = _executor_config
            retry_policy = _retry_policy

            def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
                return func(self, *args, **kwargs)

        # Set class name and module for better debugging
        GeneratedEvent.__name__ = f"{event_name}"
        GeneratedEvent.__qualname__ = f"{event_name}"
        GeneratedEvent.__module__ = func.__module__

        # Preserve original function metadata
        GeneratedEvent._original_func = func
        GeneratedEvent._event_name = event_name

        return GeneratedEvent

    return decorator


def listener(
    signal: typing.Union["SoftSignal", typing.Iterable["SoftSignal"]],
    sender: typing.Type = None,
):
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
        sender: The sender of this event. Additional keyword arguments that can be
                passed to the signal's connect method.

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
