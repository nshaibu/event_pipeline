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

    # def get_failed_events(self) -> List[Dict[str, Any]]:
    #     """Get metrics for all failed events"""
    #     metrics = telemetry.get_all_metrics()
    #     return [
    #         m.to_dict()
    #         for metric in metrics.values()
    #         for m in metric
    #         if m.status == "failed"
    #     ]
    #
    # def get_slow_events(self, threshold_seconds: float = 1.0) -> List[Dict[str, Any]]:
    #     """Get metrics for events that took longer than threshold"""
    #     metrics = telemetry.get_all_metrics()
    #     return [
    #         m.to_dict()
    #         for metric in metrics.values()
    #         for m in metric
    #         if m.duration() > threshold_seconds
    #     ]
    #
    # def get_retry_stats(self) -> Dict[str, Any]:
    #     """Get retry statistics"""
    #     metrics = telemetry.get_all_metrics()
    #     total_retries = sum(
    #         m.retry_count for metric in metrics.values() for m in metric
    #     )
    #     events_with_retries = sum(
    #         1 for metric in metrics.values() for m in metric if m.retry_count > 0
    #     )
    #
    #     return {
    #         "total_retries": total_retries,
    #         "events_with_retries": events_with_retries,
    #         "events_by_retry_count": {
    #             str(i): len(
    #                 [
    #                     m
    #                     for metric in metrics.values()
    #                     for m in metric
    #                     if m.retry_count == i
    #                 ]
    #             )
    #             for i in range(
    #                 max(
    #                     (m.retry_count for metric in metrics.values() for m in metric),
    #                     default=0,
    #                 )
    #                 + 1
    #             )
    #         },
    #     }


# Global reporter instance
reporter = TelemetryReporter()
