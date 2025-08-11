import json
import typing
from datetime import datetime
from typing import Any, Dict, List

from event_pipeline.result import ResultSet
from event_pipeline.telemetry.factory import TelemetryLoggerFactory

from .logger import AbstractTelemetryLogger, EventMetrics, Pipeline_Id


class TelemetryReporter:
    """Formats and outputs telemetry data"""

    def __init__(self):
        self.logger = None

    def format_metrics(
        self, metrics: typing.Union[ResultSet, typing.Dict[Pipeline_Id, ResultSet]]
    ) -> typing.Union[typing.List[dict], typing.Dict[str, typing.List[dict]]]:
        """Format metrics while preserving pipeline structure"""
        if isinstance(metrics, ResultSet):
            return [metric.to_dict() for metric in metrics]
        elif isinstance(metrics, dict):
            return {
                pipeline_id or "default": [metric.to_dict() for metric in result_set]
                for pipeline_id, result_set in metrics.items()
            }

    def get_all_metrics_json(self) -> str:
        """Get all metrics as JSON string"""
        self.logger = TelemetryLoggerFactory.get_logger()
        metrics = self.logger.get_all_metrics()

        formatted = self.format_metrics(metrics)
        return json.dumps(formatted, indent=2)

    def get_failed_events(self) -> List[Dict[str, Any]]:
        """Get metrics for all failed events"""
        self.logger = TelemetryLoggerFactory.get_logger()
        metrics = self.logger.get_all_metrics()

        if isinstance(metrics, ResultSet):
            return [m.to_dict() for m in metrics if m.status == "failed"]
        elif isinstance(metrics, dict):
            return [
                m.to_dict()
                for result_set in metrics.values()
                for m in result_set
                if m.status == "failed"
            ]
        return []

    def get_slow_events(self, threshold_seconds: float = 1.0) -> List[Dict[str, Any]]:
        """Get metrics for events that took longer than threshold"""
        self.logger = TelemetryLoggerFactory.get_logger()
        metrics = self.logger.get_all_metrics()

        if isinstance(metrics, ResultSet):
            return [m.to_dict() for m in metrics if m.duration() > threshold_seconds]
        elif isinstance(metrics, dict):
            return [
                m.to_dict()
                for result_set in metrics.values()
                for m in result_set
                if m.duration() > threshold_seconds
            ]
        return []

    def get_retry_stats(self) -> Dict[str, Any]:
        """Get retry statistics"""
        self.logger = TelemetryLoggerFactory.get_logger()
        metrics = self.logger.get_all_metrics()

        # Flatten metrics regardless of logger type
        all_metrics = []
        if isinstance(metrics, ResultSet):
            all_metrics = list(metrics)
        elif isinstance(metrics, dict):
            all_metrics = [m for result_set in metrics.values() for m in result_set]

        total_retries = sum(m.retry_count for m in all_metrics)
        events_with_retries = sum(1 for m in all_metrics if m.retry_count > 0)

        max_retries = max((m.retry_count for m in all_metrics), default=0)

        return {
            "total_retries": total_retries,
            "events_with_retries": events_with_retries,
            "events_by_retry_count": {
                str(i): len([m for m in all_metrics if m.retry_count == i])
                for i in range(max_retries + 1)
            },
        }


# Global reporter instance
reporter = TelemetryReporter()
