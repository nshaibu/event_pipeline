import logging
import time
import typing
import threading
from dataclasses import dataclass
from datetime import datetime

from .publisher import MetricsPublisher

logger = logging.getLogger(__name__)


@dataclass
class EventMetrics:
    """Metrics for a single event execution"""

    event_name: str
    task_id: str
    start_time: float
    end_time: typing.Optional[float] = None
    status: str = "pending"
    error: typing.Optional[str] = None
    retry_count: int = 0
    process_id: typing.Optional[int] = None

    def duration(self) -> float:
        """Calculate execution duration in seconds"""
        if not self.end_time:
            return 0
        return self.end_time - self.start_time


class TelemetryLogger:
    """
    Thread-safe telemetry logger for event pipeline monitoring.
    Tracks metrics, events, and performance data.
    """

    def __init__(self):
        self._metrics: typing.Dict[str, EventMetrics] = {}
        self._lock = threading.Lock()
        self._publishers: typing.List[MetricsPublisher] = []

    def add_publisher(self, publisher: MetricsPublisher) -> None:
        """Add a metrics publisher"""
        self._publishers.append(publisher)

    def remove_publisher(self, publisher: MetricsPublisher) -> None:
        """Remove a metrics publisher"""
        if publisher in self._publishers:
            self._publishers.remove(publisher)

    def start_event(
        self, event_name: str, task_id: str, process_id: Optional[int] = None
    ) -> None:
        """Record the start of an event execution"""
        with self._lock:
            self._metrics[task_id] = EventMetrics(
                event_name=event_name,
                task_id=task_id,
                start_time=time.time(),
                process_id=process_id,
            )
            logger.debug(f"Started tracking event: {event_name} (task_id: {task_id})")

    def end_event(self, task_id: str, error: typing.Optional[str] = None) -> None:
        """Record the end of an event execution"""
        with self._lock:
            if task_id in self._metrics:
                metrics = self._metrics[task_id]
                metrics.end_time = time.time()
                metrics.status = "failed" if error else "completed"
                metrics.error = error

                # Publish metrics
                for publisher in self._publishers:
                    try:
                        publisher.publish_event_metrics(metrics)
                    except Exception as e:
                        logger.error(f"Failed to publish metrics: {e}")

                logger.debug(
                    f"Event {metrics.event_name} {metrics.status} "
                    f"in {metrics.duration():.2f}s (task_id: {task_id})"
                )

    def record_retry(self, task_id: str) -> None:
        """Record a retry attempt for an event"""
        with self._lock:
            if task_id in self._metrics:
                self._metrics[task_id].retry_count += 1
                logger.debug(
                    f"Retry #{self._metrics[task_id].retry_count} "
                    f"for task {task_id}"
                )

    def get_metrics(self, task_id: str) -> typing.Optional[EventMetrics]:
        """Get metrics for a specific task"""
        with self._lock:
            return self._metrics.get(task_id)

    def get_all_metrics(self) -> typing.Dict[str, EventMetrics]:
        """Get all collected metrics"""
        with self._lock:
            return self._metrics.copy()


# Global telemetry logger instance
telemetry = TelemetryLogger()
