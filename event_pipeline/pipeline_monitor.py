import logging
import time
import typing
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

if typing.TYPE_CHECKING:
    from event_pipeline.pipeline import BatchPipeline

logger = logging.getLogger(__name__)


@dataclass
class PipelineExecutionMetrics:
    """
    Tracks execution metrics for batch pipeline monitoring
    """

    total_pipelines: int = 0
    started: int = 0
    completed: int = 0
    failed: int = 0
    active: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    execution_durations: List[float] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        total_finished = self.completed + self.failed
        return (self.completed / total_finished * 100) if total_finished > 0 else 0.0

    @property
    def average_duration(self) -> float:
        """Calculate average execution duration"""
        return (
            sum(self.execution_durations) / len(self.execution_durations)
            if self.execution_durations
            else 0.0
        )

    @property
    def total_duration(self) -> float:
        """Calculate total batch execution time"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return time.time() - self.start_time
        return 0.0


class MonitoringEventHandler:
    """Base class for handling monitoring events"""

    def handle_batch_started(
        self, batch: "BatchPipeline", metrics: PipelineExecutionMetrics
    ) -> None:
        """Called when batch execution starts"""
        pass

    def handle_pipeline_started(
        self, event_data: Dict, metrics: PipelineExecutionMetrics
    ) -> None:
        """Called when a pipeline starts execution"""
        pass

    def handle_pipeline_completed(
        self, event_data: Dict, metrics: PipelineExecutionMetrics
    ) -> None:
        """Called when a pipeline completes successfully"""
        pass

    def handle_pipeline_failed(
        self, event_data: Dict, metrics: PipelineExecutionMetrics
    ) -> None:
        """Called when a pipeline fails"""
        pass

    def handle_batch_finished(
        self, batch: "BatchPipeline", metrics: PipelineExecutionMetrics
    ) -> None:
        """Called when batch execution finishes"""
        pass


class LoggingEventHandler(MonitoringEventHandler):
    def __init__(self, logger_instance: logging.Logger = None):
        self.logger = logger_instance or logger

    def handle_batch_started(
        self, batch: "BatchPipeline", metrics: PipelineExecutionMetrics
    ) -> None:
        self.logger.info(
            f"Batch pipeline execution started: {batch.pipeline_template.__name__}",
            extra={"batch_id": batch.id, "total_pipelines": metrics.total_pipelines},
        )

    def handle_pipeline_started(
        self, event_data: Dict, metrics: PipelineExecutionMetrics
    ) -> None:
        self.logger.debug(
            f"Pipeline started: {event_data.get('pipeline_id')}",
            extra={
                "pipeline_id": event_data.get("pipeline_id"),
                "process_id": event_data.get("process_id"),
                "active_count": metrics.active,
            },
        )

    def handle_pipeline_completed(
        self, event_data: Dict, metrics: PipelineExecutionMetrics
    ) -> None:
        duration = event_data.get("execution_duration", 0)
        self.logger.info(
            f"Pipeline completed: {event_data.get('pipeline_id')} (Duration: {duration:.2f}s)",
            extra={
                "pipeline_id": event_data.get("pipeline_id"),
                "duration": duration,
                "success_rate": metrics.success_rate,
            },
        )

    def handle_pipeline_failed(
        self, event_data: Dict, metrics: PipelineExecutionMetrics
    ) -> None:
        self.logger.error(
            f"Pipeline failed: {event_data.get('pipeline_id')} - {event_data.get('error_message', 'Unknown error')}",
            extra={
                "pipeline_id": event_data.get("pipeline_id"),
                "error_type": event_data.get("error_type"),
                "process_id": event_data.get("process_id"),
            },
        )

    def handle_batch_finished(
        self, batch: "BatchPipeline", metrics: PipelineExecutionMetrics
    ) -> None:
        self.logger.info(
            f"Batch pipeline finished: {batch.pipeline_template.__name__} "
            f"(Success: {metrics.completed}/{metrics.total_pipelines}, "
            f"Failed: {metrics.failed}, Duration: {metrics.total_duration:.2f}s)",
            extra={
                "batch_id": batch.id,
                "success_rate": metrics.success_rate,
                "total_duration": metrics.total_duration,
            },
        )
