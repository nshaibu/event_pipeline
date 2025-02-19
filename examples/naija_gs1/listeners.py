from event_pipeline.signal.signals import *
from event_pipeline.decorators import listener
from event_pipeline.task import EventExecutionContext


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
