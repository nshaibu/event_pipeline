"""Telemetry metrics publishing system.

This module provides interfaces and implementations for publishing telemetry
metrics to various backends like Grafana, Elasticsearch, etc.
"""

import abc
import json
import logging
import typing
from datetime import datetime
from dataclasses import asdict

if typing.TYPE_CHECKING:
    from .logger import EventMetrics

logger = logging.getLogger(__name__)

# Optional dependencies
elasticsearch = None
prometheus_client = None
requests = None

try:
    import elasticsearch
except ImportError:
    pass

try:
    import prometheus_client
except ImportError:
    pass

try:
    import requests
except ImportError:
    pass


class MetricsPublisher(abc.ABC):
    """Base interface for metrics publishing adapters."""

    @abc.abstractmethod
    def publish_event_metrics(self, metrics: "EventMetrics") -> None:
        """Publish event metrics to the backend system."""
        pass

    @abc.abstractmethod
    def publish_network_metrics(self, metrics: dict) -> None:
        """Publish network operation metrics to the backend system."""
        pass

    def format_metrics(self, metrics: typing.Union["EventMetrics", dict]) -> dict:
        """Format metrics into a standardized dictionary format."""
        from .logger import EventMetrics
        if isinstance(metrics, EventMetrics):
            data = asdict(metrics)
            data.update(
                {
                    "timestamp": datetime.now().isoformat(),
                    "metric_type": "event",
                    "duration": metrics.duration(),
                }
            )
        else:
            data = {
                **metrics,
                "timestamp": datetime.now().isoformat(),
                "metric_type": "network",
            }
        return data


class ElasticsearchPublisher(MetricsPublisher):
    """Publishes metrics to Elasticsearch."""

    def __init__(
        self,
        hosts: typing.List[str],
        index_prefix: str = "event-pipeline-metrics",
        **kwargs,
    ):
        if elasticsearch is None:
            raise ImportError(
                "elasticsearch-py package is required. "
                "Install with: pip install 'event-pipeline[metrics]'"
            )

        self.client = elasticsearch.Elasticsearch(hosts, **kwargs)
        self.index_prefix = index_prefix

    def _get_index_name(self, metric_type: str) -> str:
        """Get the index name for a metric type."""
        date = datetime.now().strftime("%Y.%m.%d")
        return f"{self.index_prefix}-{metric_type}-{date}"

    def publish_event_metrics(self, metrics: "EventMetrics") -> None:
        """Publish event metrics to Elasticsearch."""
        try:
            data = self.format_metrics(metrics)
            index = self._get_index_name("event")
            self.client.index(index=index, document=data)
        except Exception as e:
            logger.error(f"Failed to publish event metrics to Elasticsearch: {e}")

    def publish_network_metrics(self, metrics: dict) -> None:
        """Publish network metrics to Elasticsearch."""
        try:
            data = self.format_metrics(metrics)
            index = self._get_index_name("network")
            self.client.index(index=index, document=data)
        except Exception as e:
            logger.error(f"Failed to publish network metrics to Elasticsearch: {e}")


class PrometheusPublisher(MetricsPublisher):
    """Publishes metrics to Prometheus."""

    def __init__(self, port: int = 9090):
        if prometheus_client is None:
            raise ImportError(
                "prometheus-client package is required. "
                "Install with: pip install 'event-pipeline[metrics]'"
            )

        self.event_duration = prometheus_client.Histogram(
            "event_duration_seconds",
            "Duration of event execution",
            ["event_name", "status"],
        )
        self.event_retries = prometheus_client.Counter(
            "event_retries_total", "Number of event retries", ["event_name"]
        )
        self.network_bytes = prometheus_client.Counter(
            "network_bytes_total",
            "Number of bytes sent/received",
            ["operation", "direction"],
        )
        self.network_latency = prometheus_client.Histogram(
            "network_latency_seconds", "Network operation latency", ["operation"]
        )

        prometheus_client.start_http_server(port)

    def publish_event_metrics(self, metrics: "EventMetrics") -> None:
        """Publish event metrics to Prometheus."""
        try:
            self.event_duration.labels(
                event_name=metrics.event_name, status=metrics.status
            ).observe(metrics.duration())

            if metrics.retry_count > 0:
                self.event_retries.labels(event_name=metrics.event_name).inc(
                    metrics.retry_count
                )
        except Exception as e:
            logger.error(f"Failed to publish event metrics to Prometheus: {e}")

    def publish_network_metrics(self, metrics: dict) -> None:
        """Publish network metrics to Prometheus."""
        try:
            operation = metrics.get("operation", "unknown")

            if "bytes_sent" in metrics:
                self.network_bytes.labels(operation=operation, direction="sent").inc(
                    metrics["bytes_sent"]
                )

            if "bytes_received" in metrics:
                self.network_bytes.labels(
                    operation=operation, direction="received"
                ).inc(metrics["bytes_received"])

            if "latency" in metrics:
                self.network_latency.labels(operation=operation).observe(
                    metrics["latency"]
                )
        except Exception as e:
            logger.error(f"Failed to publish network metrics to Prometheus: {e}")


class GrafanaCloudPublisher(MetricsPublisher):
    """Publishes metrics to Grafana Cloud using the HTTP API."""

    def __init__(
        self,
        api_key: str,
        org_slug: str,
        region: str = "prod-us-east-0",
    ):
        if requests is None:
            raise ImportError(
                "requests package is required. "
                "Install with: pip install 'event-pipeline[metrics]'"
            )

        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )

        self.base_url = f"https://grafana-{region}.grafana.net/api/v1/metrics"
        self.org_slug = org_slug

    def publish_event_metrics(self, metrics: "EventMetrics") -> None:
        """Publish event metrics to Grafana Cloud."""
        try:
            data = self.format_metrics(metrics)
            self._send_metrics("events", data)
        except Exception as e:
            logger.error(f"Failed to publish event metrics to Grafana Cloud: {e}")

    def publish_network_metrics(self, metrics: dict) -> None:
        """Publish network metrics to Grafana Cloud."""
        try:
            data = self.format_metrics(metrics)
            self._send_metrics("network", data)
        except Exception as e:
            logger.error(f"Failed to publish network metrics to Grafana Cloud: {e}")

    def _send_metrics(self, metric_type: str, data: dict) -> None:
        """Send metrics to Grafana Cloud."""
        url = f"{self.base_url}/{self.org_slug}/{metric_type}"
        response = self.session.post(url, json=data)
        response.raise_for_status()


class CompositePublisher(MetricsPublisher):
    """Publishes metrics to multiple backends simultaneously."""

    def __init__(self, publishers: typing.List[MetricsPublisher]):
        self.publishers = publishers

    def publish_event_metrics(self, metrics: "EventMetrics") -> None:
        """Publish event metrics to all configured publishers."""
        for publisher in self.publishers:
            try:
                publisher.publish_event_metrics(metrics)
            except Exception as e:
                logger.error(
                    f"Failed to publish event metrics using {publisher.__class__.__name__}: {e}"
                )

    def publish_network_metrics(self, metrics: dict) -> None:
        """Publish network metrics to all configured publishers."""
        for publisher in self.publishers:
            try:
                publisher.publish_network_metrics(metrics)
            except Exception as e:
                logger.error(
                    f"Failed to publish network metrics using {publisher.__class__.__name__}: {e}"
                )
