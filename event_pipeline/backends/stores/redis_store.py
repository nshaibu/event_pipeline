from event_pipeline.backends.connectors.redis import RedisConnector
from event_pipeline.backends.store import KeyValueStoreBackendBase


class RedisStoreBackend(KeyValueStoreBackendBase):
    connector = RedisConnector
