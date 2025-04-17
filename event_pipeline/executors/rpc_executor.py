import logging
import typing
import threading
import inspect
import xmlrpc.client
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from threading import Lock
from dataclasses import dataclass
from event_pipeline.utils import create_client_ssl_context

logger = logging.getLogger(__name__)


class XMLRPCExecutor(Executor):
    """
    RPC Executor that submits tasks to remote servers using XML-RPC protocol.
    """

    def __init__(
        self,
        host: str,
        port: int,
        max_workers: int = 4,
        use_encryption: bool = False,
        client_cert_path: typing.Optional[str] = None,
        client_key_path: typing.Optional[str] = None,
        ca_cert_path: typing.Optional[str] = None,
    ):
        """Initialize the RPC executor with configuration"""
        self._host = host
        self._port = port

        self._shutdown = False
        self._lock = Lock()
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers or 4)

        self._use_encryption = use_encryption
        self._client_cert_path = client_cert_path
        self._client_key_path = client_key_path
        self._ca_cert_path = ca_cert_path

        # create SSL context
        self.context = None
        self.protocol = "http"

        if self._use_encryption:
            self.protocol = "https"
            self.context = create_client_ssl_context(
                client_cert_path=self._client_cert_path,
                client_key_path=self._client_key_path,
                ca_certs_path=self._ca_cert_path,
            )

        # Create XML-RPC client
        self._server_url = f"{self.protocol}://{self._host}:{self._port}"
        self._proxy = xmlrpc.client.ServerProxy(
            self._server_url,
            allow_none=True,
            use_builtin_types=True,
            context=self.context,
        )

    def submit(self, fn: typing.Callable, /, *args, **kwargs) -> Future:
        """Submit a task for execution on the remote server"""
        if self._shutdown:
            raise RuntimeError("Executor has been shutdown")

        future = Future()

        # Submit task to thread pool
        submission_future = self._thread_pool.submit(
            self._submit_task, future, fn, args, kwargs
        )
        submission_future.add_done_callback(
            lambda f: f.result() if not f.cancelled() else None
        )

        return future

    def _submit_task(
        self, future: Future, fn: typing.Callable, args: tuple, kwargs: dict
    ) -> None:
        """Submit a task to the remote server"""
        try:
            # Get function source code and name
            source = inspect.getsource(fn)
            name = fn.__name__

            # Make RPC call
            try:
                result = self._proxy.execute(name, source, args, kwargs)

                # Handle error result
                if isinstance(result, dict) and result.get("error"):
                    future.set_exception(Exception(result["error"]))
                else:
                    future.set_result(result)

            except xmlrpc.client.Fault as e:
                logger.error(f"XML request fault {str(e)}", exc_info=e)
                future.set_exception(Exception(f"RPC error: {e}"))
            except xmlrpc.client.ProtocolError as e:
                logger.error(f"XML request protocol error {str(e)}", exc_info=e)
                future.set_exception(Exception(f"Protocol error: {e}"))
            except Exception as e:
                logger.error(f"XML request error {str(e)}", exc_info=e)
                future.set_exception(e)

        except Exception as e:
            logger.error(f"Error submitting task: {e}", exc_info=True)
            future.set_exception(e)

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """Clean shutdown of the executor"""
        with self._lock:
            self._shutdown = True
            self._thread_pool.shutdown(wait=wait, cancel_futures=cancel_futures)
