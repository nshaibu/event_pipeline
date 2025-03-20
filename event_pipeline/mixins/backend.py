import typing
import logging
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

        backend_config = CONFIG.RESULT_BACKEND_CONFIG
        connector_config = backend_config.get("CONNECTOR_CONFIG", {})
        try:
            self._backend = import_string(backend_config["ENGINE"])
        except Exception as e:
            logger.error(f"Error importing backend {backend_config}: {e}")
        if self._connector is None:
            self._connector = self._backend(**connector_config)

    def get_schema_name(self) -> str:
        return self.__class__.__name__

    def _connect(self, **kwargs):
        if self._connector is None:
            self._connector = self._backend(**kwargs)
        return self._connector

    def _disconnect(self):
        if self._connector is not None:
            self._connector.close()

    def save(self):
        self._connector.insert_record(
            schema_name=self.get_schema_name(), record_key=self.id, record=self
        )

    def reload(self):
        self._connector.reload_record(self.get_schema_name(), self)

    def delete(self):
        self._connector.delete_record(
            schema_name=self.get_schema_name(), record_key=self.id
        )

    def update(self):
        self._connector.update_record(
            schema_name=self.get_schema_name(), record_key=self.id, record=self
        )
