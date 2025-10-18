import logging
import typing
import grpc
from concurrent import futures
from .base import BaseManager
from nexus.protos import task_pb2, task_pb2_grpc
from nexus.executors.message import TaskMessage

logger = logging.getLogger(__name__)


class TaskExecutorServicer(task_pb2_grpc.TaskExecutorServicer):
    """Implementation of TaskExecutor service."""

    def Execute(self, request, context):
        """Execute a task and return the result."""
        try:
            # Deserialize arguments
            fn, _ = TaskMessage.deserialize(request.fn)
            args, _ = TaskMessage.deserialize(request.args)
            kwargs, _ = TaskMessage.deserialize(request.kwargs)

            # Execute function
            result = fn(*args, **kwargs)

            # Serialize result
            serialized_result = TaskMessage.serialize_object(result)

            return task_pb2.TaskResponse(success=True, result=serialized_result)

        except Exception as e:
            logger.error(
                f"Error executing task {request.task_id}, name: {request.name}: {str(e)}",
                exc_info=e,
            )
            serialized_result = TaskMessage.serialize_object(e)
            return task_pb2.TaskResponse(
                success=False, error=str(e), result=serialized_result
            )

    def ExecuteStream(self, request, context):
        """Execute a task and stream status updates."""
        try:
            # Initial status
            yield task_pb2.TaskStatus(
                status=task_pb2.TaskStatus.PENDING, message="Task received"
            )

            # Deserialize arguments
            fn, _ = TaskMessage.deserialize(request.fn)
            args, _ = TaskMessage.deserialize(request.args)
            kwargs, _ = TaskMessage.deserialize(request.kwargs)

            yield task_pb2.TaskStatus(
                status=task_pb2.TaskStatus.RUNNING, message="Task started"
            )

            # Execute with arguments
            result = fn(*args, **kwargs)

            # Serialize result
            serialized_result = TaskMessage.serialize_object(result)

            # Send completion
            yield task_pb2.TaskStatus(
                status=task_pb2.TaskStatus.COMPLETED,
                result=serialized_result,
                message="Task completed",
            )

        except Exception as e:
            logger.error(
                f"Error in streaming task {request.task_id}: {str(e)}", exc_info=e
            )
            serialized_result = TaskMessage.serialize_object(e)
            yield task_pb2.TaskStatus(
                status=task_pb2.TaskStatus.FAILED,
                message=str(e),
                result=serialized_result,
            )


class GRPCManager(BaseManager):
    """
    gRPC server that handles remote task execution requests.
    """

    def __init__(
        self,
        host: str,
        port: int,
        max_workers: int = 10,
        use_encryption: bool = False,
        server_cert_path: typing.Optional[str] = None,
        server_key_path: typing.Optional[str] = None,
        require_client_cert: bool = False,
        client_ca_path: typing.Optional[str] = None,
    ) -> None:
        super().__init__(host=host, port=port)
        self._max_workers = max_workers
        self._use_encryption = use_encryption
        self._server_cert_path = server_cert_path
        self._server_key_path = server_key_path
        self._require_client_cert = require_client_cert
        self._client_ca_path = client_ca_path
        self._server = None
        self._shutdown = False

    def start(self, *args, **kwargs) -> None:
        """Start the gRPC server"""
        try:
            # Create server
            self._server = grpc.server(
                futures.ThreadPoolExecutor(max_workers=self._max_workers)
            )

            # Add servicer
            task_pb2_grpc.add_TaskExecutorServicer_to_server(
                TaskExecutorServicer(), self._server
            )

            # Configure encryption if enabled
            if self._use_encryption:
                if not (self._server_cert_path and self._server_key_path):
                    raise ValueError(
                        "Server certificate and key required for encryption"
                    )

                # Load server credentials
                with open(self._server_key_path, "rb") as f:
                    private_key = f.read()
                with open(self._server_cert_path, "rb") as f:
                    certificate_chain = f.read()

                # Load client CA if required
                root_certificates = None
                if self._require_client_cert:
                    if not self._client_ca_path:
                        raise ValueError(
                            "Client CA required when client cert is required"
                        )
                    with open(self._client_ca_path, "rb") as f:
                        root_certificates = f.read()

                server_credentials = grpc.ssl_server_credentials(
                    ((private_key, certificate_chain),),
                    root_certificates=root_certificates,
                    require_client_auth=self._require_client_cert,
                )
                port = self._server.add_secure_port(
                    f"{self._host}:{self._port}", server_credentials
                )
            else:
                port = self._server.add_insecure_port(f"{self._host}:{self._port}")

            # Start server
            self._server.start()
            logger.info(f"gRPC server listening on {self._host}:{port}")

            # Wait for shutdown
            self._server.wait_for_termination()

        except Exception as e:
            logger.error(f"Error starting gRPC server: {e}")
            raise

    def shutdown(self) -> None:
        """Shutdown the gRPC server"""
        if self._server:
            self._server.stop(grace=5)  # 5 seconds grace period
            self._server = None
