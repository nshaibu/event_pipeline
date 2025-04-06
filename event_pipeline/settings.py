MAX_EVENT_RETRIES = 5
MAX_EVENT_BACKOFF_FACTOR = 0.05
MAX_EVENT_BACKOFF = 100

MAX_BATCH_PROCESSING_WORKERS = 4

RESULT_BACKEND_CONFIG = {
    "ENGINE": "event_pipeline.backends.stores.redis_store.RedisStoreBackend",
    "CONNECTOR_CONFIG": {
        "host": "localhost",
        "port": 6379,
    },
    "CONNECTION_MODE": "pooled",  # "single" or "pooled" or "auto"
    "MAX_CONNECTIONS": 10,  # Only used in pooled mode
    "CONNECTION_TIMEOUT": 30,  # Seconds to wait for connection acquisition
    "IDLE_TIMEOUT": 300,  # Seconds before closing idle connections
}
