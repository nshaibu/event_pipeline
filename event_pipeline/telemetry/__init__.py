"""
Telemetry module for event-pipeline.

This module provides telemetry and metrics collection for the event pipeline,
tracking execution times, success/failure rates, retries, and other metrics.

Usage:
    from event_pipeline.telemetry import (
        monitor_events,
        get_metrics,
        ElasticsearchPublisher,
        PrometheusPublisher,
        GrafanaCloudPublisher
    )

    # Set up metrics publishing
    es_publisher = ElasticsearchPublisher(["localhost:9200"])
    prometheus_publisher = PrometheusPublisher(port=9090)

    # Enable telemetry collection with publishers
    monitor_events([es_publisher, prometheus_publisher])

    # After running your pipeline, metrics will be automatically published
    # You can still get metrics programmatically
    metrics_json = get_metrics()
    print(metrics_json)
"""

import typing

from event_pipeline.telemetry.logger import AbstractTelemetryLogger

from .collector import register_collectors
from .factory import TelemetryLoggerFactory
from .network import network_telemetry
from .publisher import (CompositePublisher, ElasticsearchPublisher,
                        GrafanaCloudPublisher, MetricsPublisher,
                        PrometheusPublisher)
from .reporter import reporter


def monitor_events(
    publishers: typing.List[MetricsPublisher] = None,
    logger_class: typing.Type[AbstractTelemetryLogger] = None,
) -> None:
    """
    Start monitoring pipeline events and collecting metrics.

    Args:
        publishers: Optional list of MetricsPublisher instances to publish metrics
    """

    if logger_class:
        TelemetryLoggerFactory.set_logger_class(logger_class)

    telemetry = TelemetryLoggerFactory.get_logger()

    if publishers:
        for pub in publishers:
            telemetry.add_publisher(pub)
    register_collectors()


def get_metrics() -> str:
    """Get all collected metrics as JSON string"""
    return reporter.get_all_metrics_json()


def get_failed_events() -> list:
    """Get metrics for all failed events"""
    return reporter.get_failed_events()


def get_slow_events(
    threshold_seconds: float = 1.0,
) -> typing.List[typing.Dict[str, typing.Any]]:
    """Get metrics for events that took longer than threshold"""
    return reporter.get_slow_events(threshold_seconds)


def get_retry_stats() -> typing.Dict[str, typing.Any]:
    """Get retry statistics"""
    return reporter.get_retry_stats()


def get_failed_network_ops() -> typing.Dict[str, typing.Any]:
    """Get metrics for failed network operations"""
    return network_telemetry.get_failed_operations()


def get_slow_network_ops(
    threshold_seconds: float = 1.0,
) -> typing.Dict[str, typing.Any]:
    """Get metrics for slow network operations"""
    return network_telemetry.get_slow_operations(threshold_seconds)


__all__ = [
    "monitor_events",
    "get_metrics",
    "get_failed_events",
    "get_slow_events",
    "get_retry_stats",
    "get_failed_network_ops",
    "get_slow_network_ops",
    "MetricsPublisher",
    "ElasticsearchPublisher",
    "PrometheusPublisher",
    "GrafanaCloudPublisher",
    "CompositePublisher",
]
