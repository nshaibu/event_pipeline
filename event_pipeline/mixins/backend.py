import typing
import logging
import threading
from event_pipeline.exceptions import ObjectExistError
from event_pipeline.import_utils import import_string
from event_pipeline.conf import ConfigLoader
from event_pipeline.mixins.identity import ObjectIdentityMixin
from event_pipeline.backends.store import KeyValueStoreBackendBase


logger = logging.getLogger(__name__)

CONFIG = ConfigLoader.get_lazily_loaded_config()


class BackendIntegrationMixin(ObjectIdentityMixin):

    def __model_init__(self) -> None:
        ObjectIdentityMixin.__init__(self)

        self._backend: typing.Optional[typing.Type[KeyValueStoreBackendBase]] = None
        self._connector = None

        self._lock = threading.RLock()

        backend_config = CONFIG.RESULT_BACKEND_CONFIG
        connector_config = backend_config.get("CONNECTOR_CONFIG", {})
        try:
            self._backend = import_string(backend_config["ENGINE"])
        except Exception as e:
            logger.error(f"Error importing backend {backend_config}: {e}")
            raise

        try:
            if self._connector is None:
                self._connector = self._backend(**connector_config)
        except Exception as e:
            logger.error(f"Failed to initialize backend connector: {e}")
            raise

        self.save()

    def __getstate__(self):
        """
        Prepare object for pickling by removing the lock.
        """
        state = self.__dict__.copy()
        # Remove the lock since it can't be pickled
        if "_lock" in state:
            del state["_lock"]
        return state

    def __setstate__(self, state):
        """
        Restore object state after unpickling and recreate the lock.
        """
        self.__dict__.update(state)
        # Recreate the lock
        self._lock = threading.RLock()

    def get_schema_name(self) -> str:
        return self.__class__.__name__

    def _connect(self, **kwargs):
        if self._lock is None:
            self._lock = threading.RLock()
        with self._lock:
            if self._connector is None:
                self._connector = self._backend(**kwargs)

        return self._connector

    def _disconnect(self):
        with self._lock:
            if self._connector is not None:
                self._connector.close()
                self._connector = None

    def save(self):
        if not self._connector:
            logger.warning("Attempting to save without an active connector")
            return

        with self._lock:
            try:
                self._connector.insert_record(
                    schema_name=self.get_schema_name(), record_key=self.id, record=self
                )
            except ObjectExistError:
                self._connector.update_record(
                    schema_name=self.get_schema_name(), record_key=self.id, record=self
                )

    def reload(self):
        if not self._connector:
            logger.warning("Attempting to reload without an active connector")
            return
        self._connector.reload_record(self.get_schema_name(), self)

    def delete(self):
        if not self._connector:
            logger.warning("Attempting to delete without an active connector")
            return

        with self._lock:
            self._connector.delete_record(
                schema_name=self.get_schema_name(), record_key=self.id
            )

    def update(self):
        if not self._connector:
            logger.warning("Attempting to update without an active connector")
            return
        with self._lock:
            self._connector.update_record(
                schema_name=self.get_schema_name(), record_key=self.id, record=self
            )

    def __del__(self):
        if self._connector is not None:
            self._connector.close()
