import types
import typing
import logging
import threading
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler
from .base import BaseManager
from event_pipeline.utils import create_server_ssl_context

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

                self._server.socket = context.wrap_socket(sock=self._server.socket, server_side=True)

            # Register functions
            self._server.register_function(self.execute, "execute")

            logger.info(f"RPC server listening on {self._host}:{self._port}")

            # Start serving
            self._server.serve_forever()

        except Exception as e:
            logger.error(f"Error starting RPC server: {e}")
            raise

    def execute(self, name: str, source: str, args: tuple, kwargs: dict):
        """
        Execute a function received via RPC.

        Args:
            name: Function name
            source: Function source code
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            Function result or error dict
        """
        try:
            # Create function from source
            scope = {}
            exec(source, scope)
            fn = scope[name]

            # Execute function
            result = fn(*args, **kwargs)
            return result

        except Exception as e:
            logger.error(f"Error executing {name}: {e}")
            return {"error": str(e)}

    def shutdown(self) -> None:
        """Shutdown the RPC server"""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
