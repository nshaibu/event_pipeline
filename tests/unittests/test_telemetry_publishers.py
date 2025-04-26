import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

from ..utils import is_package_installed

from event_pipeline.telemetry.logger import EventMetrics
from event_pipeline.telemetry.publisher import (
    MetricsPublisher,
    ElasticsearchPublisher,
    PrometheusPublisher,
    GrafanaCloudPublisher,
    CompositePublisher,
)


class TestMetricsPublishers(unittest.TestCase):
    def setUp(self):
        self.test_metrics = EventMetrics(
            event_name="TestEvent",
            task_id="test-123",
            start_time=datetime.now().timestamp(),
            end_time=datetime.now().timestamp() + 1.5,
            status="completed",
            process_id=1234,
        )

        self.test_network_metrics = {
            "operation": "remote_call",
            "host": "localhost",
            "port": 8080,
            "bytes_sent": 1000,
            "bytes_received": 500,
            "latency": 0.25,
        }

    @pytest.mark.skipif(is_package_installed("elasticsearch") is False, reason="Elasticsearch not installed")
    @patch("elasticsearch.Elasticsearch")
    def test_elasticsearch_publisher(self, mock_es):
        # Setup mock
        mock_client = MagicMock()
        mock_es.return_value = mock_client

        # Create publisher
        publisher = ElasticsearchPublisher(["localhost:9200"])

        # Test event metrics
        publisher.publish_event_metrics(self.test_metrics)
        mock_client.index.assert_called_once()

        # Verify data format
        call_args = mock_client.index.call_args[1]
        self.assertTrue("event" in call_args["index"])
        self.assertEqual(call_args["document"]["event_name"], "TestEvent")
        self.assertEqual(call_args["document"]["status"], "completed")

    @pytest.mark.skipif(is_package_installed("prometheus_client") is False, reason="Prometheus not installed")
    @patch("prometheus_client.start_http_server")
    @patch("prometheus_client.Histogram")
    @patch("prometheus_client.Counter")
    def test_prometheus_publisher(self, mock_counter, mock_histogram, mock_start):
        publisher = PrometheusPublisher(port=9090)

        # Test event metrics
        publisher.publish_event_metrics(self.test_metrics)

        # Verify metrics recording
        mock_histogram.return_value.labels.assert_called_with(
            event_name="TestEvent", status="completed"
        )
        mock_histogram.return_value.labels.return_value.observe.assert_called_once()

    @patch("requests.Session")
    def test_grafana_cloud_publisher(self, mock_session):
        mock_session.return_value.post = MagicMock()

        publisher = GrafanaCloudPublisher(api_key="test-key", org_slug="test-org")

        # Test event metrics
        publisher.publish_event_metrics(self.test_metrics)

        # Verify API call
        mock_session.return_value.post.assert_called_once()
        call_args = mock_session.return_value.post.call_args
        self.assertIn("/events", call_args[0][0])

        # Test network metrics
        publisher.publish_network_metrics(self.test_network_metrics)
        self.assertEqual(mock_session.return_value.post.call_count, 2)

    def test_composite_publisher(self):
        # Create mock publishers
        mock_pub1 = MagicMock(spec=MetricsPublisher)
        mock_pub2 = MagicMock(spec=MetricsPublisher)

        # Create composite publisher
        publisher = CompositePublisher([mock_pub1, mock_pub2])

        # Test event metrics
        publisher.publish_event_metrics(self.test_metrics)
        mock_pub1.publish_event_metrics.assert_called_once_with(self.test_metrics)
        mock_pub2.publish_event_metrics.assert_called_once_with(self.test_metrics)

        # Test network metrics
        publisher.publish_network_metrics(self.test_network_metrics)
        mock_pub1.publish_network_metrics.assert_called_once_with(
            self.test_network_metrics
        )
        mock_pub2.publish_network_metrics.assert_called_once_with(
            self.test_network_metrics
        )

    def test_error_handling(self):
        # Create mock publisher that raises an exception
        mock_pub = MagicMock(spec=MetricsPublisher)
        mock_pub.publish_event_metrics.side_effect = Exception("Test error")

        # Create composite publisher
        publisher = CompositePublisher([mock_pub])

        # Test that exception is caught and handled
        try:
            publisher.publish_event_metrics(self.test_metrics)
        except Exception:
            self.fail("Exception was not properly handled")
