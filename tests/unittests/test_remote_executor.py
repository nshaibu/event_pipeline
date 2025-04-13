import unittest
import socket
import threading
import tempfile
import os
from unittest.mock import Mock, patch
from event_pipeline.manager.remote import RemoteTaskManager
from event_pipeline.executors.remote_executor import (
    RemoteExecutor,
    TaskMessage,
)


def dummy_task(x, y):
    return x + y


class TestRemoteExecutor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create temporary SSL certificates for testing
        cls.cert_dir = tempfile.mkdtemp()
        cls.server_cert = os.path.join(cls.cert_dir, "server.crt")
        cls.server_key = os.path.join(cls.cert_dir, "server.key")
        cls.client_cert = os.path.join(cls.cert_dir, "client.crt")
        cls.client_key = os.path.join(cls.cert_dir, "client.key")
        cls.ca_cert = os.path.join(cls.cert_dir, "ca.crt")

        # Generate test certificates here...
        # In real tests, you would use OpenSSL to generate these

    def setUp(self):
        self.host = "localhost"
        self.port = 12345

        # Start task manager in a separate thread
        self.task_manager = RemoteTaskManager(
            host=self.host,
            port=self.port,
            cert_path=self.server_cert,
            key_path=self.server_key,
            ca_certs_path=self.ca_cert,
            require_client_cert=True,
        )
        self.server_thread = threading.Thread(target=self.task_manager.start)
        self.server_thread.daemon = True
        self.server_thread.start()

    def tearDown(self):
        self.task_manager.shutdown()
        self.server_thread.join(timeout=1)

    @classmethod
    def tearDownClass(cls):
        # Clean up temporary certificate files
        import shutil

        shutil.rmtree(cls.cert_dir)

    def test_executor_initialization(self):
        executor = RemoteExecutor(
            host=self.host,
            port=self.port,
            client_cert_path=self.client_cert,
            client_key_path=self.client_key,
            ca_cert_path=self.ca_cert,
        )
        self.assertFalse(executor._shutdown)
        self.assertTrue(executor._worker.is_alive())
        executor.shutdown()

    def test_task_submission_with_encryption(self):
        executor = RemoteExecutor(
            host=self.host,
            port=self.port,
            use_encryption=True,
            client_cert_path=self.client_cert,
            client_key_path=self.client_key,
            ca_cert_path=self.ca_cert,
        )

        future = executor.submit(dummy_task, 5, 3)
        result = future.result(timeout=5)
        self.assertEqual(result, 8)

        executor.shutdown()

    def test_task_submission_without_encryption(self):
        executor = RemoteExecutor(host=self.host, port=self.port, use_encryption=False)

        future = executor.submit(dummy_task, 10, 5)
        result = future.result(timeout=5)
        self.assertEqual(result, 15)

        executor.shutdown()

    def test_multiple_task_submission(self):
        executor = RemoteExecutor(
            host=self.host,
            port=self.port,
            use_encryption=True,
            client_cert_path=self.client_cert,
            client_key_path=self.client_key,
            ca_cert_path=self.ca_cert,
        )

        futures = []
        expected_results = []

        for i in range(5):
            futures.append(executor.submit(dummy_task, i, i * 2))
            expected_results.append(i * 3)

        actual_results = [f.result(timeout=5) for f in futures]
        self.assertEqual(actual_results, expected_results)

        executor.shutdown()

    def test_executor_shutdown(self):
        executor = RemoteExecutor(host=self.host, port=self.port)

        executor.shutdown()
        self.assertTrue(executor._shutdown)

        with self.assertRaises(RuntimeError):
            executor.submit(dummy_task, 1, 2)

    @patch("socket.socket")
    def test_connection_error_handling(self, mock_socket):
        mock_socket.side_effect = socket.error("Connection refused")

        executor = RemoteExecutor(host=self.host, port=self.port)

        future = executor.submit(dummy_task, 1, 2)
        with self.assertRaises(socket.error):
            future.result(timeout=5)

        executor.shutdown()


class TestRemoteTaskManager(unittest.TestCase):
    def setUp(self):
        self.host = "localhost"
        self.port = 12346

    def test_task_manager_initialization(self):
        manager = RemoteTaskManager(
            host=self.host,
            port=self.port,
            cert_path="server.crt",
            key_path="server.key",
        )
        self.assertFalse(manager._shutdown)
        self.assertIsNone(manager._sock)

    @patch("socket.socket")
    def test_task_manager_start_stop(self, mock_socket):
        manager = RemoteTaskManager(self.host, self.port)

        # Start server in a thread
        server_thread = threading.Thread(target=manager.start)
        server_thread.daemon = True
        server_thread.start()

        # Give it time to start
        import time

        time.sleep(0.1)

        # Verify socket was created and bound
        self.assertTrue(mock_socket.called)
        mock_socket.return_value.bind.assert_called_with((self.host, self.port))
        mock_socket.return_value.listen.assert_called_with(5)

        # Shutdown
        manager.shutdown()
        server_thread.join(timeout=1)
        self.assertTrue(manager._shutdown)
        mock_socket.return_value.close.assert_called()
