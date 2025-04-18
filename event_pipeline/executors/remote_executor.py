import socket
import ssl
import pickle
import logging
import typing
import concurrent.futures
import threading
import queue
import zlib
import cloudpickle
from concurrent.futures import Executor
from multiprocessing.reduction import ForkingPickler
from event_pipeline.conf import ConfigLoader
from event_pipeline.utils import (
    send_data_over_socket,
    receive_data_from_socket,
    create_client_ssl_context,
)
from event_pipeline.executors.message import TaskMessage

logger = logging.getLogger(__name__)

CONF = ConfigLoader.get_lazily_loaded_config()

DEFAULT_TIMEOUT = CONF.DEFAULT_CONNECTION_TIMEOUT
CHUNK_SIZE = CONF.DATA_CHUNK_SIZE
BACKLOG_SIZE = CONF.CONNECTION_BACKLOG_SIZE
QUEUE_SIZE = CONF.DATA_QUEUE_SIZE


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

        context = create_client_ssl_context(
            client_cert_path=self._client_cert_path,
            client_key_path=self._client_key_path,
            ca_certs_path=self._ca_cert_path,
        )

        return context.wrap_socket(sock, server_hostname=self._host)

    def _send_task(self, task_message: TaskMessage) -> typing.Any:
        """Send a task to the remote server and get the result"""
        try:
            with self._create_secure_connection() as sock:

                data_size = send_data_over_socket(
                    sock, data=task_message.serialize(), chunk_size=CHUNK_SIZE
                )

                logger.debug(
                    "Sent task %s of size %d bytes to server", task_message, data_size
                )

                # Receive result
                result_data = receive_data_from_socket(sock, chunk_size=CHUNK_SIZE)

                logger.debug(
                    f"Receive {len(result_data)} bytes from {self._host}:{self._port}"
                )

                try:
                    result, _ = TaskMessage.deserialize(result_data)
                except (zlib.error, pickle.UnpicklingError) as e:
                    logger.error(f"Failed to decompress message: {str(e)}", exc_info=e)
                    result = ValueError(f"Invalid task result data received: {str(e)}")
                except ModuleNotFoundError as e:
                    logger.error(
                        f"Failed to decompress task result data: {str(e)}", exc_info=e
                    )
                    result = e

                if isinstance(result, Exception):
                    raise result

                return result
        except Exception as e:
            logger.error(f"Error executing remote task: {str(e)}")
            raise

    def task_queue(self) -> queue.Queue:
        """Separated for easy mocking"""
        return self._tasks

    def _process_queue(self):
        """Process tasks from the queue"""
        while not self._shutdown:
            try:
                task_id, future, task_message = self.task_queue().get(timeout=0.1)
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

    def shutdown(self, wait: bool = True, cancel_futures: bool = False):
        """Shutdown the executor"""
        self._shutdown = True
        if wait:
            self._worker.join()
