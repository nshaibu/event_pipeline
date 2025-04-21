import unittest
import time
from event_pipeline import EventBase
from event_pipeline.telemetry import (
    monitor_events,
    get_metrics,
    get_failed_events,
    get_slow_events,
    get_retry_stats,
    get_failed_network_ops,
    get_slow_network_ops,
)
from event_pipeline.telemetry.logger import telemetry
from event_pipeline.telemetry.network import network_telemetry
from event_pipeline.executors.remote_executor import RemoteExecutor


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        # Reset telemetry state before each test
        telemetry._metrics.clear()
        network_telemetry._metrics.clear()

    def test_event_tracking(self):
        task_id = "test-task-1"
        telemetry.start_event("TestEvent", task_id)
        time.sleep(0.1)  # Simulate work
        telemetry.end_event(task_id)

        metrics = telemetry.get_metrics(task_id)
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.event_name, "TestEvent")
        self.assertEqual(metrics.status, "completed")
        self.assertGreater(metrics.duration(), 0)

    def test_failed_event_tracking(self):
        task_id = "test-task-2"
        telemetry.start_event("FailedEvent", task_id)
        telemetry.end_event(task_id, error="Test error")

        metrics = telemetry.get_metrics(task_id)
        self.assertEqual(metrics.status, "failed")
        self.assertEqual(metrics.error, "Test error")

        failed_events = get_failed_events()
        self.assertEqual(len(failed_events), 1)
        self.assertEqual(failed_events[0]["event_name"], "FailedEvent")

    def test_retry_tracking(self):
        task_id = "test-task-3"
        telemetry.start_event("RetryEvent", task_id)
        telemetry.record_retry(task_id)
        telemetry.record_retry(task_id)
        telemetry.end_event(task_id)

        metrics = telemetry.get_metrics(task_id)
        self.assertEqual(metrics.retry_count, 2)

        retry_stats = get_retry_stats()
        self.assertEqual(retry_stats["total_retries"], 2)
        self.assertEqual(retry_stats["events_with_retries"], 1)

    def test_network_telemetry(self):
        task_id = "test-network-1"
        network_telemetry.start_operation(task_id, "localhost", 8080)
        time.sleep(0.1)  # Simulate network operation
        network_telemetry.end_operation(task_id, bytes_sent=1000, bytes_received=500)

        metrics = network_telemetry.get_metrics(task_id)
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.host, "localhost")
        self.assertEqual(metrics.port, 8080)
        self.assertEqual(metrics.bytes_sent, 1000)
        self.assertEqual(metrics.bytes_received, 500)
        self.assertGreater(metrics.latency(), 0)

    def test_failed_network_operation(self):
        task_id = "test-network-2"
        network_telemetry.start_operation(task_id, "localhost", 8080)
        network_telemetry.end_operation(task_id, error="Connection refused")

        failed_ops = get_failed_network_ops()
        self.assertEqual(len(failed_ops), 1)
        self.assertEqual(failed_ops[task_id].error, "Connection refused")

    def test_metrics_json_format(self):
        task_id = "test-task-4"
        telemetry.start_event("JsonTest", task_id)
        telemetry.end_event(task_id)

        metrics_json = get_metrics()
        self.assertIn("JsonTest", metrics_json)
        self.assertIn(task_id, metrics_json)
