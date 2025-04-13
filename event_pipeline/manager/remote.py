import socket
import ssl
import pickle
import logging
import typing
import concurrent.futures
from .base import BaseManager

logger = logging.getLogger(__name__)


# Constants for remote execution
DEFAULT_TIMEOUT = 30  # seconds
CHUNK_SIZE = 4096
BACKLOG_SIZE = 5
QUEUE_SIZE = 1000


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
        """
        super().__init__(host=host, port=port)
        self._cert_path = cert_path
        self._key_path = key_path
        self._ca_certs_path = ca_certs_path
        self._require_client_cert = require_client_cert

        self._shutdown = False
        self._process_pool = concurrent.futures.ProcessPoolExecutor()

    def _create_server_socket(self) -> socket.socket:
        """Create and configure the server socket"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if not (self._cert_path and self._key_path):
            return sock

        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=self._cert_path, keyfile=self._key_path)

        if self._ca_certs_path:
            context.load_verify_locations(self._ca_certs_path)
            if self._require_client_cert:
                context.verify_mode = ssl.CERT_REQUIRED

        return context.wrap_socket(sock, server_side=True)

    def _handle_client(self, client_sock: socket.socket, client_addr: tuple):
        """Handle a client connection"""
        try:
            # Receive task message
            msg_size = int.from_bytes(client_sock.recv(8), "big")
            msg_data = b""
            while len(msg_data) < msg_size:
                chunk = client_sock.recv(min(CHUNK_SIZE, msg_size - len(msg_data)))
                if not chunk:
                    return
                msg_data += chunk

            task_message = pickle.loads(msg_data)

            # Execute task
            try:
                result = task_message.fn(*task_message.args, **task_message.kwargs)
            except Exception as e:
                result = e

            # Send result back
            result_data = pickle.dumps(result)
            client_sock.sendall(len(result_data).to_bytes(8, "big"))
            client_sock.sendall(result_data)

        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {str(e)}", exc_info=e)
        finally:
            try:
                client_sock.close()
            except:
                pass

    def start(self):
        try:
            self._sock = self._create_server_socket()
            self._sock.bind((self._host, self._port))
            self._sock.listen(BACKLOG_SIZE)

            logger.info(f"Task manager listening on {self._host}:{self._port}")

            while not self._shutdown:
                try:
                    client_sock, client_addr = self._sock.accept()
                    self._process_pool.submit(
                        self._handle_client, client_sock, client_addr
                    )
                except socket.timeout:
                    continue

        except Exception as e:
            logger.error(f"Error in task manager: {str(e)}", exc_info=e)
        finally:
            self.shutdown()

    def shutdown(self):
        self._shutdown = True
        if self._sock:
            try:
                self._sock.close()
            except:
                pass
        self._process_pool.shutdown()
