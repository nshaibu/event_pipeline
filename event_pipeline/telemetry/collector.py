from typing import Optional
from ..signal.signals import (
    event_execution_init,
    event_execution_start,
    event_execution_end,
    event_execution_retry,
    event_execution_retry_done,
    pipeline_execution_start,
    pipeline_execution_end,
)
from ..base import EventBase
from ..task import EventExecutionContext
from .logger import telemetry


class MetricsCollector:
    """Collects metrics by listening to pipeline signals"""

    @staticmethod
    def on_event_init(sender: EventBase, **kwargs) -> None:
        """Handle event initialization"""
        task_id = kwargs.get("task_id")
        if task_id:
            telemetry.start_event(
                event_name=sender.__class__.__name__,
                task_id=task_id,
                process_id=kwargs.get("process_id"),
            )

    @staticmethod
    def on_event_end(
        sender: EventBase, execution_context: EventExecutionContext, **kwargs
    ) -> None:
        """Handle event completion"""
        error = None
        if execution_context._errors:
            error = str(execution_context._errors[0])
        task_id = kwargs.get("task_id")
        if task_id:
            telemetry.end_event(task_id, error=error)

    @staticmethod
    def on_event_retry(
        sender: EventBase, task_id: str, retry_count: int, max_attempts: int, **kwargs
    ) -> None:
        """Handle event retry"""
        telemetry.record_retry(task_id)


def register_collectors():
    """Register all metric collectors with the signal system"""
    event_execution_init.connect(MetricsCollector.on_event_init)
    event_execution_end.connect(MetricsCollector.on_event_end)
    event_execution_retry.connect(MetricsCollector.on_event_retry)
