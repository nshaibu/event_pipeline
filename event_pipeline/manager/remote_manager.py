import socket
import types
import zlib
import ssl
import sys
import os
import inspect
import typing
import pickle
import logging
from pathlib import Path
from importlib import import_module
from multiprocessing.reduction import ForkingPickler
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from .base import BaseManager
from event_pipeline import EventBase
from event_pipeline.conf import ConfigLoader
from event_pipeline.utils import (
    send_data_over_socket,
    receive_data_from_socket,
    create_server_ssl_context,
)

logger = logging.getLogger(__name__)

CONF = ConfigLoader.get_lazily_loaded_config()

DEFAULT_TIMEOUT = CONF.DEFAULT_CONNECTION_TIMEOUT
CHUNK_SIZE = CONF.DATA_CHUNK_SIZE
BACKLOG_SIZE = CONF.CONNECTION_BACKLOG_SIZE
QUEUE_SIZE = CONF.DATA_QUEUE_SIZE
PROJECT_ROOT = CONF.PROJECT_ROOT_DIR


class RemoteTaskManager(BaseManager):
    """
    Server that receives and executes tasks from RemoteExecutor clients.
    Supports SSL/TLS encryption and client certificate verification.
    """

    def __init__(
        self,
        host: str,
        port: int,
        cert_path: typing.Optional[str] = None,
        key_path: typing.Optional[str] = None,
        ca_certs_path: typing.Optional[str] = None,
        require_client_cert: bool = False,
        socket_timeout: float = DEFAULT_TIMEOUT,
    ):
        """
        Initialize the task manager.

        Args:
            host: Host to bind to
            port: Port to listen on
            cert_path: Path to server certificate file
            key_path: Path to server private key file
            ca_certs_path: Path to CA certificates for client verification
            require_client_cert: Whether to require client certificates
            socket_timeout: Socket timeout in seconds
        """
        super().__init__(host=host, port=port)
        self._cert_path = cert_path
        self._key_path = key_path
        self._ca_certs_path = ca_certs_path
        self._require_client_cert = require_client_cert
        self._socket_timeout = socket_timeout

        self._shutdown = False
        self._sock: typing.Optional[socket.socket] = None
        # self._process_context = mp.get_context("spawn")
        # self._process_pool = ProcessPoolExecutor(mp_context=self._process_context)
        self._thread_pool = ThreadPoolExecutor(max_workers=4)

    @classmethod
    def auto_load_all_task_modules(cls):
        """
        Auto-discover and load all modules containing event classes that inherit from EventBase.
        Searches through the project directory for Python modules and registers event classes.
        """
        project_root = PROJECT_ROOT
        logger.info(f"Searching for event modules in: {project_root}")

        discovered_events: typing.Set[typing.Type] = set()

        def is_event_class(obj: typing.Type) -> bool:
            """Check if an object is a class inheriting from EventBase"""
            return (
                inspect.isclass(obj)
                and hasattr(obj, "__module__")
                and EventBase in [base for base in inspect.getmro(obj)[1:]]
            )

        def explore_module(module_name: str) -> None:
            """Explore a module for event classes"""
            try:
                module = import_module(module_name)
                for name, obj in inspect.getmembers(module):
                    if is_event_class(obj):
                        discovered_events.add(obj)
                        logger.debug(
                            f"Discovered event class: {obj.__module__}.{obj.__name__}"
                        )
            except Exception as e:
                logger.warning(f"Failed to load module {module_name}: {e}")

        # Walk through all Python packages in the project
        for root, dirs, files in os.walk(str(project_root)):
            # Skip __pycache__ and virtual environment directories
            dirs[:] = [d for d in dirs if not d.startswith(("__", "."))]

            if "__init__.py" in files:
                # Calculate the module path relative to project root
                rel_path = Path(root).relative_to(project_root)
                module_path = str(rel_path).replace(os.sep, ".")
                if module_path:
                    explore_module(module_path)

        # Register discovered event modules
        for event_class in discovered_events:
            module = sys.modules.get(event_class.__module__)
            if module:
                cls.register_task_module(event_class.__module__, module)
                logger.info(f"Registered event module: {event_class.__module__}")

        logger.info(f"Discovered {len(discovered_events)} event classes")

    @staticmethod
    def register_task_module(module_name: str, module: types.ModuleType) -> None:
        """
        Register a module containing event classes for task execution.

        Args:
            module_name: The fully qualified module name
            module: The module object to register
        """
        if module_name not in sys.modules:
            sys.modules[module_name] = module
            logger.debug(f"Registered module in sys.modules: {module_name}")

    def _create_server_socket(self) -> socket.socket:
        """Create and configure the server socket with proper timeout and SSL if enabled"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self._socket_timeout)

        if not (self._cert_path and self._key_path):
            return sock

        try:
            context = create_server_ssl_context(
                cert_path=self._cert_path,
                key_path=self._key_path,
                ca_certs_path=self._ca_certs_path,
                require_client_cert=self._require_client_cert,
            )

            return context.wrap_socket(sock, server_side=True)
        except (ssl.SSLError, OSError) as e:
            logger.error(f"Failed to create SSL context: {str(e)}", exc_info=e)
            raise

    def _handle_client(
        self, client_sock: socket.socket, client_addr: typing.Tuple[str, int]
    ) -> None:
        """Handle a client connection"""
        client_info = f"{client_addr[0]}:{client_addr[1]}"
        logger.info(f"New client connection from {client_info}")

        try:
            client_sock.settimeout(self._socket_timeout)
            exception = None

            # Receive task message
            try:
                msg_data = receive_data_from_socket(client_sock, chunk_size=CHUNK_SIZE)

                decompressed_data = zlib.decompress(msg_data)
                task_message = ForkingPickler.loads(decompressed_data)
            except (zlib.error, pickle.UnpicklingError) as e:
                logger.error(f"Failed to decompress message: {str(e)}", exc_info=e)
                exception = ValueError(f"Invalid task data received: {str(e)}")
            except ModuleNotFoundError as e:
                logger.error(f"Failed to decompress task data: {str(e)}", exc_info=e)
                exception = e

            # Execute task
            if exception is None:
                try:
                    result = task_message.fn(*task_message.args, **task_message.kwargs)
                except Exception as e:
                    logger.error(
                        f"Task execution failed for client {client_info}: {str(e)}",
                        exc_info=e,
                    )
                    result = e
            else:
                result = exception

            # Send result back
            send_data_over_socket(client_sock, result, chunk_size=CHUNK_SIZE)

            logger.info(f"Successfully completed task for client {client_info}")

        except Exception as e:
            logger.error(f"Error handling client {client_info}: {str(e)}", exc_info=e)
        finally:
            try:
                client_sock.close()
                logger.debug(f"Closed connection from {client_info}")
            except Exception:
                pass

    def start(self) -> None:
        """Start the task manager with proper error handling"""
        try:
            self._sock = self._create_server_socket()
            self._sock.bind((self._host, self._port))
            self._sock.listen(BACKLOG_SIZE)

            logger.info(f"Task manager listening on {self._host}:{self._port}")

            while not self._shutdown:
                try:
                    client_sock, client_addr = self._sock.accept()
                    self._thread_pool.submit(
                        self._handle_client, client_sock, client_addr
                    )
                except socket.timeout:
                    continue  # Allow checking shutdown flag
                except Exception as e:
                    if not self._shutdown:
                        logger.error(
                            f"Error accepting client connection: {str(e)}", exc_info=e
                        )

        except Exception as e:
            logger.error(f"Fatal error in task manager: {str(e)}", exc_info=e)
            raise
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Gracefully shutdown the task manager"""
        if self._shutdown:
            return

        self._shutdown = True
        logger.info("Shutting down task manager...")

        if self._sock:
            try:
                self._sock.close()
            except Exception as e:
                logger.error(f"Error closing server socket: {str(e)}", exc_info=e)

        if self._thread_pool:
            try:
                self._thread_pool.shutdown(wait=True)
            except Exception as e:
                logger.error(f"Error shutting down thread pool: {str(e)}", exc_info=e)

        logger.info("Task manager shutdown complete")
