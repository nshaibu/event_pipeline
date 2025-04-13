import unittest
import threading
from unittest.mock import Mock, patch
from event_pipeline.executors.remote_event import RemoteEvent
from event_pipeline.base import ExecutorInitializerConfig, EventResult
from event_pipeline.manager.remote import RemoteTaskManager


class TestRemoteEvent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start test server
        cls.manager = RemoteTaskManager(
            host="localhost", port=12346, require_client_cert=False
        )
        cls.server_thread = threading.Thread(target=cls.manager.start)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.manager.shutdown()
        cls.server_thread.join(timeout=1)

    def test_remote_event_initialization(self):
        class TestEvent(RemoteEvent):
            executor_config = ExecutorInitializerConfig(
                host="localhost", port=12346, use_encryption=False
            )

            def _execute_remote(self, *args, **kwargs):
                return True, {"status": "success"}

        event = TestEvent(execution_context={}, task_id="test-1")

        self.assertIsInstance(event, RemoteEvent)
        self.assertEqual(event._task_id, "test-1")
        self.assertEqual(len(event._futures), 0)

    def test_remote_event_execution(self):
        class TestEvent(RemoteEvent):
            executor_config = ExecutorInitializerConfig(
                host="localhost", port=12346, use_encryption=False
            )

            def _execute_remote(self, data):
                return {"processed": data["value"] * 2}

        event = TestEvent(execution_context={}, task_id="test-2")

        success, result = event.process({"value": 21})
        self.assertTrue(success)
        self.assertEqual(result["processed"], 42)

    def test_remote_event_failure(self):
        class TestEvent(RemoteEvent):
            executor_config = ExecutorInitializerConfig(
                host="localhost", port=12346, use_encryption=False
            )

            def _execute_remote(self, *args, **kwargs):
                raise ValueError("Test error")

        event = TestEvent(execution_context={}, task_id="test-3")

        success, result = event.process()
        self.assertFalse(success)
        self.assertIsInstance(result, ValueError)
        self.assertEqual(str(result), "Test error")

    def test_remote_event_result_handling(self):
        class TestEvent(RemoteEvent):
            executor_config = ExecutorInitializerConfig(
                host="localhost", port=12346, use_encryption=False
            )

            def _execute_remote(self, *args, **kwargs):
                return EventResult(
                    error=False,
                    task_id="test-4",
                    event_name="TestEvent",
                    content={"status": "ok"},
                    call_params={},
                    init_params={},
                )

        event = TestEvent(execution_context={}, task_id="test-4")

        success, result = event.process()
        self.assertTrue(success)
        self.assertEqual(result["status"], "ok")

    @patch("event_pipeline.executors.remote_executor.RemoteExecutor.submit")
    def test_remote_event_timeout(self, mock_submit):
        from concurrent.futures import TimeoutError

        # Mock future that times out
        future = Mock()
        future.result.side_effect = TimeoutError()
        mock_submit.return_value = future

        class TestEvent(RemoteEvent):
            executor_config = ExecutorInitializerConfig(
                host="localhost", port=12346, use_encryption=False, timeout=1
            )

            def _execute_remote(self, *args, **kwargs):
                return {"status": "never reached"}

        event = TestEvent(execution_context={}, task_id="test-5")

        success, result = event.process()
        self.assertFalse(success)
        self.assertIsInstance(result, TimeoutError)
