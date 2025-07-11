import typing
import logging
import threading
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import Binary
from .base import BaseManager
from event_pipeline.utils import create_server_ssl_context
from event_pipeline.executors.message import TaskMessage
from event_pipeline.utils import send_data_over_socket

logger = logging.getLogger(__name__)


class XMLRPCManager(BaseManager):
    """
    XML-RPC server that handles remote task execution requests.
    """

    def __init__(
        self,
        host: str,
        port: int,
        use_encryption: bool = False,
        cert_path: typing.Optional[str] = None,
        key_path: typing.Optional[str] = None,
        ca_certs_path: typing.Optional[str] = None,
        require_client_cert: bool = False,
    ) -> None:
        super().__init__(host=host, port=port)
        self._cert_path = cert_path
        self._key_path = key_path
        self._ca_certs_path = ca_certs_path
        self._require_client_cert = require_client_cert
        self._use_encryption = use_encryption

        self._server: typing.Optional[SimpleXMLRPCServer] = None
        self._shutdown = False
        self._lock = threading.Lock()

    def start(self, *args, **kwargs) -> None:
        """Start the RPC server"""
        try:
            # Create server
            self._server = SimpleXMLRPCServer(
                (self._host, self._port),
                allow_none=True,
                logRequests=True,
            )

            if self._use_encryption:
                if not (self._cert_path and self._key_path):
                    raise ValueError(
                        "Server certificate and key required for encryption"
                    )

                context = create_server_ssl_context(
                    cert_path=self._cert_path,
                    key_path=self._key_path,
                    ca_certs_path=self._ca_certs_path,
                    require_client_cert=self._require_client_cert,
                )

                self._server.socket = context.wrap_socket(
                    sock=self._server.socket, server_side=True
                )

            # Register functions
            self._server.register_function(self.execute, "execute")

            logger.info(f"RPC server listening on {self._host}:{self._port}")

            # Start serving
            self._server.serve_forever()

        except Exception as e:
            logger.error(f"Error starting RPC server: {e}")
            raise

    def execute(self, name: str, message: Binary) -> typing.Any:
        """
        Execute a function received via RPC.

        Args:
            name: Function name
            message: Function pickled body
        Returns:
            Function result or error dict
        """
        try:
            task_message, _ = TaskMessage.deserialize(message.data)

            # Execute function
            result = task_message.fn(*task_message.args, **task_message.kwargs)

        except Exception as e:
            logger.error(f"Error executing {name}: {e}", exc_info=e)
            result = e

        return TaskMessage.serialize_object(result)

    def shutdown(self) -> None:
        """Shutdown the RPC server"""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
