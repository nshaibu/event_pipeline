"""Network telemetry for tracking remote operations."""

import logging
import time
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NetworkMetrics:
    """Metrics for a network operation"""

    task_id: str
    host: str
    port: int
    start_time: float
    end_time: Optional[float] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    error: Optional[str] = None
    operation: str = "remote_call"

    def latency(self) -> float:
        """Calculate operation latency in seconds"""
        if not self.end_time:
            return 0
        return self.end_time - self.start_time


class NetworkTelemetry:
    """
    Thread-safe telemetry for network operations.
    Tracks latency, throughput, and errors.
    """

    def __init__(self):
        self._metrics: Dict[str, NetworkMetrics] = {}
        self._lock = threading.Lock()
        self._publishers: List[Any] = []  # Will hold MetricsPublisher instances

    def add_publisher(self, publisher: Any) -> None:
        """Add a metrics publisher"""
        self._publishers.append(publisher)

    def remove_publisher(self, publisher: Any) -> None:
        """Remove a metrics publisher"""
        if publisher in self._publishers:
            self._publishers.remove(publisher)

    def start_operation(
        self, task_id: str, host: str, port: int, operation: str = "remote_call"
    ) -> None:
        """Record the start of a network operation"""
        with self._lock:
            self._metrics[task_id] = NetworkMetrics(
                task_id=task_id,
                host=host,
                port=port,
                start_time=time.time(),
                operation=operation,
            )
            logger.debug(
                f"Started tracking network operation to {host}:{port} "
                f"(task_id: {task_id})"
            )

    def end_operation(
        self,
        task_id: str,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Record the end of a network operation"""
        with self._lock:
            if task_id in self._metrics:
                metrics = self._metrics[task_id]
                metrics.end_time = time.time()
                metrics.bytes_sent = bytes_sent
                metrics.bytes_received = bytes_received
                metrics.error = error

                # Publish metrics
                for publisher in self._publishers:
                    try:
                        publisher.publish_network_metrics(
                            {
                                "task_id": metrics.task_id,
                                "host": metrics.host,
                                "port": metrics.port,
                                "operation": metrics.operation,
                                "latency": metrics.latency(),
                                "bytes_sent": metrics.bytes_sent,
                                "bytes_received": metrics.bytes_received,
                                "error": metrics.error,
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to publish network metrics: {e}")

                logger.debug(
                    f"Network operation completed in {metrics.latency():.2f}s "
                    f"(task_id: {task_id})"
                )

    def get_metrics(self, task_id: str) -> Optional[NetworkMetrics]:
        """Get metrics for a specific operation"""
        with self._lock:
            return self._metrics.get(task_id)

    def get_all_metrics(self) -> Dict[str, NetworkMetrics]:
        """Get all collected metrics"""
        with self._lock:
            return self._metrics.copy()

    def get_failed_operations(self) -> Dict[str, NetworkMetrics]:
        """Get metrics for all failed operations"""
        with self._lock:
            return {
                task_id: metrics
                for task_id, metrics in self._metrics.items()
                if metrics.error is not None
            }

    def get_slow_operations(
        self, threshold_seconds: float = 1.0
    ) -> Dict[str, NetworkMetrics]:
        """Get metrics for operations that took longer than threshold"""
        with self._lock:
            return {
                task_id: metrics
                for task_id, metrics in self._metrics.items()
                if metrics.latency() > threshold_seconds
            }


# Global network telemetry instance
network_telemetry = NetworkTelemetry()
