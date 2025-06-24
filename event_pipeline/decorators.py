import typing
import asyncio
import warnings
from functools import wraps
from concurrent.futures import Executor
from .base import EventBase, RetryPolicy, ExecutorInitializerConfig
from .executors.default_executor import DefaultExecutor

# import typing
# import warnings
# from abc import ABC, abstractmethod
# from dataclasses import dataclass, field
# from functools import wraps
# from typing import Any, Callable, Dict, Optional, Type, TypeVar, Generic
# from enum import Enum

# Type definitions
F = typing.TypeVar('F', bound=typing.Callable[..., typing.Any])
T = typing.TypeVar('T')

# class ExecutionStatus(Enum):
#     """Status of event execution."""
#     PENDING = "pending"
#     RUNNING = "running"
#     COMPLETED = "completed"
#     FAILED = "failed"
#     RETRYING = "retrying"
#
#
# @dataclass
# class ExecutionResult(Generic[T]):
#     """Result of event execution."""
#     status: ExecutionStatus
#     value: Optional[T] = None
#     error: Optional[Exception] = None
#     execution_time_ms: Optional[int] = None
#     retry_count: int = 0
#     metadata: Dict[str, Any] = field(default_factory=dict)
#
#
# @dataclass
# class RetryPolicy:
#     """Configuration for retry behavior."""
#     max_attempts: int = 3
#     base_delay_ms: int = 1000
#     max_delay_ms: int = 30000
#     backoff_multiplier: float = 2.0
#     retry_on_exceptions: tuple = (Exception,)
#
#
# @dataclass
# class ExecutorConfig:
#     """Configuration for executor behavior."""
#     timeout_ms: Optional[int] = None
#     max_concurrent: Optional[int] = None
#     priority: int = 0
#     metadata: Dict[str, Any] = field(default_factory=dict)


# class Event(ABC):
#     """Base class for all events."""
#
#     def __init__(self,
#                  executor: Executor,
#                  retry_policy: Optional[RetryPolicy] = None,
#                  executor_config: Optional[ExecutorConfig] = None):
#         self.executor = executor
#         self.retry_policy = retry_policy or RetryPolicy()
#         self.executor_config = executor_config or ExecutorConfig()
#         self._execution_context: Dict[str, Any] = {}
#
#     @abstractmethod
#     async def _execute_impl(self, *args, **kwargs) -> Any:
#         """Implementation of the event logic."""
#         pass
#
#     async def execute(self, *args, **kwargs) -> ExecutionResult:
#         """Execute the event using the configured executor."""
#         return await self.executor.execute(self, *args, **kwargs)
#
#     def with_executor(self, executor: Executor) -> 'Event':
#         """Create a copy of this event with a different executor."""
#         return self.__class__(
#             executor=executor,
#             retry_policy=self.retry_policy,
#             executor_config=self.executor_config
#         )
#
#     def with_retry_policy(self, retry_policy: RetryPolicy) -> 'Event':
#         """Create a copy of this event with a different retry policy."""
#         return self.__class__(
#             executor=self.executor,
#             retry_policy=retry_policy,
#             executor_config=self.executor_config
#         )
#
#
# class EventRegistry:
#     """Registry for managing event types."""
#
#     def __init__(self):
#         self._events: Dict[str, Type[Event]] = {}
#
#     def register(self, name: str, event_class: Type[Event]) -> None:
#         """Register an event type."""
#         if name in self._events:
#             warnings.warn(f"Event '{name}' is being overridden", UserWarning)
#         self._events[name] = event_class
#
#     def get(self, name: str) -> Optional[Type[Event]]:
#         """Get an event type by name."""
#         return self._events.get(name)
#
#     def list_events(self) -> Dict[str, Type[Event]]:
#         """List all registered events."""
#         return self._events.copy()
#
#
# # Global registry instance
# _event_registry = EventRegistry()


def event(
        name: typing.Optional[str] = None,
        executor: typing.Optional[typing.Type[Executor]] = None,
        retry_policy: typing.Optional[RetryPolicy] = None,
        executor_config: typing.Optional[ExecutorInitializerConfig] = None
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
        def process_data(data: dict) -> str:
            # Process the data
            return "processed"

        # Usage
        event_instance = process_data(DefaultExecutor())
        result = await event_instance.execute({"key": "value"})
    """

    def decorator(func: F) -> typing.Type[EventBase]:
        event_name = name or func.__name__
        executor_class = executor or DefaultExecutor
        _retry_policy = retry_policy or RetryPolicy
        _executor_config = executor_config or ExecutorInitializerConfig()
        import pdb;pdb.set_trace()

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


# # Improved factory functions for common patterns
# class EventFactory:
#     """Factory for creating events with common configurations."""
#
#     @staticmethod
#     def quick_event(func: Callable) -> Type[Event]:
#         """Create a simple event with default settings."""
#         return event()(func)
#
#     @staticmethod
#     def resilient_event(max_attempts: int = 5, base_delay_ms: int = 1000) -> Callable:
#         """Create an event with retry capabilities."""
#         return event(
#             retry_policy=RetryPolicy(
#                 max_attempts=max_attempts,
#                 base_delay_ms=base_delay_ms
#             )
#         )
#
#     @staticmethod
#     def high_priority_event(priority: int = 10) -> Callable:
#         """Create a high-priority event."""
#         return event(
#             executor_config=ExecutorConfig(priority=priority)
#         )
#
#
# # Usage examples and utilities
# def get_event_by_name(name: str) -> Optional[Type[Event]]:
#     """Get a globally registered event by name."""
#     return _event_registry.get(name)
#
#
# def list_registered_events() -> Dict[str, Type[Event]]:
#     """List all globally registered events."""
#     return _event_registry.list_events()
#
#
# # Example usage
# if __name__ == "__main__":
#     import asyncio
#
#
#     # Example 1: Simple event
#     @event()
#     def simple_task(message: str) -> str:
#         return f"Processed: {message}"
#
#
#     # Example 2: Event with retry policy
#     @event(retry_policy=RetryPolicy(max_attempts=3))
#     def resilient_task(data: dict) -> str:
#         if not data.get("valid"):
#             raise ValueError("Invalid data")
#         return "Success"
#
#
#     # Example 3: Globally registered event
#     @event(register_globally=True, name="global_processor")
#     def global_task(value: int) -> int:
#         return value * 2
#
#
#     async def main():
#         # Create event instances
#         simple_event = simple_task()
#         resilient_event = resilient_task()
#
#         # Execute events
#         result1 = await simple_event.execute("Hello World")
#         print(f"Simple task result: {result1.value}")
#
#         result2 = await resilient_event.execute({"valid": True})
#         print(f"Resilient task result: {result2.value}")
#
#         # Use globally registered event
#         global_event_class = get_event_by_name("global_processor")
#         if global_event_class:
#             global_event = global_event_class()
#             result3 = await global_event.execute(42)
#             print(f"Global task result: {result3.value}")
#
#         # List all registered events
#         print(f"Registered events: {list(list_registered_events().keys())}")
#
#
#     # Run the example
#     asyncio.run(main())


# def event(
#     executor: typing.Type[Executor] = DefaultExecutor,
#     retry_policy: typing.Union[RetryPolicy, typing.Dict[str, typing.Any]] = None,
#     executor_config: typing.Union[
#         ExecutorInitializerConfig, typing.Dict[str, typing.Any]
#     ] = None,
# ):
#
#     def worker(func):
#
#         @wraps(func)
#         def inner(self, *args, **kwargs):
#             event_ref = self
#             return func(*args, **kwargs)
#
#         namespace = {
#             "__module__": func.__module__,
#             "executor": executor,
#             "retry_policy": retry_policy,
#             "executor_config": executor_config,
#             "execution_context": None,
#             "previous_result": None,
#             "stop_on_exception": False,
#             "process": inner,
#         }
#
#         _event = type(func.__name__, (EventBase,), namespace)
#         globals()[func.__name__] = _event
#
#         @wraps(func)
#         def task(*args, **kwargs):
#             warnings.warn(
#                 "This is an event that must be executed by an executor", Warning
#             )
#             return func(*args, **kwargs)
#
#         return task
#
#     return worker


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
