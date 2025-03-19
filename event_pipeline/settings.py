MAX_EVENT_RETRIES = 5
MAX_EVENT_BACKOFF_FACTOR = 0.05


MAX_BATCH_PROCESSING_WORKERS = 4

RESULT_BACKEND_CONFIG = {
    "ENGINE": "event_pipeline.backends.stores.inmemory_store.InMemoryKeyValueStoreBackend",
}
