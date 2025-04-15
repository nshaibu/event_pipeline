import socket
import ssl
import pickle
import logging
import typing
import concurrent.futures
import threading
import queue
import zlib
import time
from io import BytesIO
from concurrent.futures import Executor
from dataclasses import dataclass
from multiprocessing.reduction import ForkingPickler

# from pathlib import Path
# from multiprocessing.reduction import ForkingPickler
# from cryptography.hazmat.primitives import hashes, serialization
# from cryptography.hazmat.primitives.asymmetric import padding, rsa
# from cryptography.exceptions import InvalidKey

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds
CHUNK_SIZE = 4096
BACKLOG_SIZE = 5
QUEUE_SIZE = 1000


@dataclass
class TaskMessage:
    """Message format for task communication"""

    task_id: str
    fn: typing.Callable
    args: tuple
    kwargs: dict
    client_cert: typing.Optional[bytes] = None
    encrypted: bool = False


class RemoteExecutor(Executor):
    """
    A secure remote task executor that sends tasks to a remote server for execution.
    Supports SSL/TLS encryption and client certificate verification.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        timeout: int = DEFAULT_TIMEOUT,
        use_encryption: bool = False,
        client_cert_path: typing.Optional[str] = None,
        client_key_path: typing.Optional[str] = None,
        ca_cert_path: typing.Optional[str] = None,
    ):
        """
        Initialize the remote executor.

        Args:
            host: Remote server hostname/IP
            port: Remote server port
            timeout: Connection timeout in seconds
            use_encryption: Whether to use SSL/TLS encryption
            client_cert_path: Path to client certificate file
            client_key_path: Path to client private key file
            ca_cert_path: Path to CA certificate file for server verification
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._use_encryption = use_encryption
        self._client_cert_path = client_cert_path
        self._client_key_path = client_key_path
        self._ca_cert_path = ca_cert_path

        self._shutdown = False
        self._tasks = queue.Queue(QUEUE_SIZE)
        self._futures = {}
        self._lock = threading.Lock()

        # Start worker thread
        self._worker = threading.Thread(target=self._process_queue)
        self._worker.daemon = True
        self._worker.start()

    def _create_secure_connection(self) -> socket.socket:
        """Create a secure socket connection to the remote server"""
        sock = socket.create_connection((self._host, self._port), self._timeout)

        if not self._use_encryption:
            return sock

        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        if self._ca_cert_path:
            context.load_verify_locations(self._ca_cert_path)

        if self._client_cert_path and self._client_key_path:
            context.load_cert_chain(
                certfile=self._client_cert_path, keyfile=self._client_key_path
            )

        return context.wrap_socket(sock, server_hostname=self._host)

    @staticmethod
    def _send_task_in_chunks(
        client_socket: socket.socket, task_message: TaskMessage
    ) -> int:
        data = ForkingPickler.dumps(task_message, protocol=pickle.HIGHEST_PROTOCOL)
        compressed_data = zlib.compress(data)
        data_size = len(compressed_data)
        client_socket.sendall(data_size.to_bytes(8, "big"))

        stream_fd = BytesIO(compressed_data)

        sent = 0
        while sent < data_size:
            chunk = stream_fd.read(CHUNK_SIZE)
            if not chunk:
                break
            client_socket.sendall(chunk)
            sent += len(chunk)

        return sent

    @staticmethod
    def _receive_result_in_chunks(client_socket: socket.socket) -> bytes:
        result_size = int.from_bytes(client_socket.recv(8), "big")
        result_data = b""
        while len(result_data) < result_size:
            chunk = client_socket.recv(min(CHUNK_SIZE, result_size - len(result_data)))
            if not chunk:
                raise ConnectionError("Connection closed by server")
            result_data += chunk
        return result_data

    def _send_task(self, task_message: TaskMessage) -> typing.Any:
        """Send a task to the remote server and get the result"""
        try:
            with self._create_secure_connection() as sock:
                now = time.time()
                data_size = self._send_task_in_chunks(sock, task_message)

                logger.debug(
                    f"Successfully sent {data_size} bytes to {self._host}:{self._port} "
                    f"and it took {time.time() - now:.2f} seconds"
                )

                # Receive result
                result_data = self._receive_result_in_chunks(sock)

                logger.debug(
                    f"Receive {len(result_data)} bytes from {self._host}:{self._port}"
                )

                result = pickle.loads(result_data)
                if isinstance(result, Exception):
                    raise result
                return result

        except Exception as e:
            logger.error(f"Error executing remote task: {str(e)}")
            raise

    def _process_queue(self):
        """Process tasks from the queue"""
        while not self._shutdown:
            try:
                task_id, future, task_message = self._tasks.get(timeout=0.1)
                if not future.set_running_or_notify_cancel():
                    continue

                try:
                    result = self._send_task(task_message)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error in task processing thread: {str(e)}")
                raise

    def submit(
        self, fn: typing.Callable, /, *args, **kwargs
    ) -> concurrent.futures.Future:
        """Submit a task for execution on the remote server"""
        if self._shutdown:
            raise RuntimeError("Executor has been shutdown")

        future = concurrent.futures.Future()
        task_id = str(id(future))

        task_message = TaskMessage(
            task_id=task_id,
            fn=fn,
            args=args,
            kwargs=kwargs,
            encrypted=self._use_encryption,
        )

        with self._lock:
            self._futures[task_id] = future
            self._tasks.put((task_id, future, task_message))

        return future

    def shutdown(self, wait: bool = True):
        """Shutdown the executor"""
        self._shutdown = True
        if wait:
            self._worker.join()
