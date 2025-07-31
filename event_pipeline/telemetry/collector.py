import typing

from event_pipeline.signal.signals import (event_execution_end,
                                           event_execution_init,
                                           event_execution_retry,
                                           event_execution_retry_done,
                                           event_execution_start,
                                           pipeline_execution_end,
                                           pipeline_execution_start)

from .logger import telemetry

if typing.TYPE_CHECKING:
    from event_pipeline.base import EventBase
    from event_pipeline.task import EventExecutionContext


class MetricsCollector:
    """Collects metrics by listening to pipeline signals"""

    @staticmethod
    def on_event_init(sender: "EventExecutionContext", **kwargs) -> None:
        """Handle event initialization"""

        event = kwargs.get("event")
        #TODO: after the refactor make sure the make use of this id
        pipeline_id = kwargs.get("pipeline_id")

        if event:
            telemetry.start_event(
                event_name=event.__class__.__name__,
                task_id=event._task_id,
                process_id=kwargs.get("process_id"),
            )

    @staticmethod
    def on_event_end(
        sender: "EventExecutionContext",
        execution_context: "EventExecutionContext",
        **kwargs,
    ) -> None:
        """Handle event completion"""
        error = None
        if execution_context._errors:
            error = str(execution_context._errors[0])
        event = kwargs.get("event")
        if event:
            telemetry.end_event(event._task_id, event.__class__.__name__, error=error)

    @staticmethod
    def on_event_retry(
        sender: "EventBase", task_id: str, max_attempts: int, **kwargs
    ) -> None:
        """Handle event retry"""
        event = kwargs.get("event")
        telemetry.record_retry(task_id, event.__class__.__name__)


def register_collectors():
    """Register all metric collectors with the signal system"""
    from event_pipeline.task import EventExecutionContext

    event_execution_init.connect(
        listener=MetricsCollector.on_event_init, sender=EventExecutionContext
    )
    event_execution_end.connect(
        listener=MetricsCollector.on_event_end, sender=EventExecutionContext
    )
    event_execution_retry.connect(
        listener=MetricsCollector.on_event_retry, sender=EventExecutionContext
    )
