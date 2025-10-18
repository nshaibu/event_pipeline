from nexus.signal.signals import *
from nexus.decorators import listener
from nexus.task import EventExecutionContext


@listener(
    [
        event_execution_init,
        event_execution_end,
        event_execution_retry_done,
        event_execution_retry,
        event_execution_start,
    ],
    sender=EventExecutionContext,
)
def event_execution_start(*args, **kwargs):
    print(f"Event signals: {args}, {kwargs}")


@listener(event_execution_cancelled, sender=EventExecutionContext)
def event_execution_cancelled(*args, **kwargs):
    print(f"Event cancelled signal: {args}, {kwargs}")
