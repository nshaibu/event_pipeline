import typing
from event_pipeline.mixins.identity import ObjectIdentityMixin
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.backends.stores.inmemory_store import InMemoryKeyValueStoreBackend


class BackendIntegrationMixin(ObjectIdentityMixin):
    backend: typing.ClassVar[typing.Type[KeyValueStoreBackendBase]] = (
        InMemoryKeyValueStoreBackend
    )

    def __model_init__(self) -> None:
        ObjectIdentityMixin.__init__(self)

        self._connector = None
        # if self._connector is None:
        # self._connector = self.backend()

    def get_schema_name(self) -> str:
        return self.__class__.__name__

    def _connect(self, **kwargs):
        if self._connector is None:
            self._connector = self.backend(**kwargs)
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
