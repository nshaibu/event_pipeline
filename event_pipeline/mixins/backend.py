import typing
import logging
from event_pipeline.exceptions import ObjectExistError
from event_pipeline.import_utils import import_string
from event_pipeline.conf import ConfigLoader
from event_pipeline.exceptions import StopProcessingError
from event_pipeline.mixins.identity import ObjectIdentityMixin
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.mixins.utils.connector import (
    ConnectorManagerFactory,
    ConnectionMode,
    BaseConnectorManager,
    connector_action_register,
)


logger = logging.getLogger(__name__)

CONFIG = ConfigLoader.get_lazily_loaded_config()


class BackendIntegrationMixin(ObjectIdentityMixin):
    _connector_manager: typing.ClassVar[typing.Optional[BaseConnectorManager]] = None

    def __model_init__(self) -> None:
        ObjectIdentityMixin.__init__(self)

        self._backend: typing.Optional[typing.Type[KeyValueStoreBackendBase]] = None

        backend_config = CONFIG.RESULT_BACKEND_CONFIG
        connector_config = backend_config.get("CONNECTOR_CONFIG", {})
        try:
            self._backend = import_string(backend_config["ENGINE"])
        except Exception as e:
            logger.error(f"Error importing backend {backend_config}: {e}")
            raise StopProcessingError(
                f"Error importing backend {backend_config}: {e}"
            ) from e

        try:
            # Initialize the connector manager if not already created
            if self._connector_manager is None:
                # Get connection mode from config or auto-detect
                connection_mode_str = backend_config.get("CONNECTION_MODE", "auto")
                connection_mode = None
                if connection_mode_str != "auto":
                    connection_mode = ConnectionMode(connection_mode_str)

                # Create appropriate connector manager
                self.__class__._connector_manager = (
                    ConnectorManagerFactory.create_manager(
                        connector_class=self._backend,
                        connector_config=connector_config,
                        connection_mode=connection_mode,
                        max_connections=backend_config.get("MAX_CONNECTIONS", 10),
                        connection_timeout=backend_config.get("CONNECTION_TIMEOUT", 30),
                        idle_timeout=backend_config.get("IDLE_TIMEOUT", 300),
                    )
                )

            self.release_connection(self._connector_manager.get_connection())
        except Exception as e:
            logger.error(f"Failed to initialize backend connector: {e}")
            raise StopProcessingError(
                f"Failed to initialize backend connector: {e}"
            ) from e

        self.save()

    def with_connection(self, method, *args, **kwargs):
        """
        Execute a function with a connection from the manager.
        Args:
            method: The function to execute, which will be passed a connection as first arg
            *args: Additional arguments to pass to the function
            **kwargs: Additional keyword arguments to pass to the function
        Returns:
            The result of the function execution
        """
        # For pooled managers that support it, use the retry mechanism
        if hasattr(self._connector_manager, "execute_with_retry"):
            return self._connector_manager.execute_with_retry(method, *args, **kwargs)

        # For single connection managers, just get the connection and execute
        connector = self.get_connection()
        try:
            return method(*args, connector=connector, **kwargs)
        finally:
            self.release_connection(connector)

    def get_connection(self):
        """
        Get a connection from the manager.
        Returns:
            A connection
        """
        return self._connector_manager.get_connection()

    def release_connection(self, connection):
        """
        Release a connection back to the manager.
        Args:
            connection: The connection to release
        """
        self._connector_manager.release_connection(connection)

    def __getstate__(self):
        """
        Prepare object for pickling by removing the lock.
        """
        state = self.__dict__.copy()
        init_params: typing.Optional[typing.Dict[str, typing.Any]] = state.pop(
            "init_params", None
        )
        state.pop("_connector", None)
        backend = state.pop("_backend", None)

        state["_backend"] = backend.__name__ if backend is not None else None

        if init_params:
            execution_context = init_params.get("execution_context")
            if execution_context and not isinstance(execution_context, str):
                init_params["execution_context"] = execution_context.id
        else:
            init_params = {"execution_context": {}}
        state["init_params"] = init_params
        return state

    def __setstate__(self, state):
        """
        Restore object state after unpickling and recreate the lock.
        """
        init_params = state.pop("init_params", None)
        call_params = state.pop("call_params", None)

        self.__dict__.update(state)

    def get_schema_name(self) -> str:
        return self.__class__.__name__

    @connector_action_register
    def save(self, connector: KeyValueStoreBackendBase):
        try:
            connector.insert_record(
                schema_name=self.get_schema_name(), record_key=self.id, record=self
            )
        except ObjectExistError:
            connector.update_record(
                schema_name=self.get_schema_name(), record_key=self.id, record=self
            )

    @connector_action_register
    def reload(self, connector: KeyValueStoreBackendBase):
        connector.reload_record(self.get_schema_name(), self)

    @connector_action_register
    def delete(self, connector: KeyValueStoreBackendBase):
        connector.delete_record(schema_name=self.get_schema_name(), record_key=self.id)

    @connector_action_register
    def update(self, connector: KeyValueStoreBackendBase):
        connector.update_record(
            schema_name=self.get_schema_name(), record_key=self.id, record=self
        )

    # def __del__(self):
    #     if getattr(self, "_connector", None) is not None:
    #         self.connector.close()
