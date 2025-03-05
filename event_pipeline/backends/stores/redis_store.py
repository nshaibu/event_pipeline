import typing
import pickle
from event_pipeline.backends.connectors.redis import RedisConnector
from event_pipeline.backends.store import KeyValueStoreBackendBase


class RedisStoreBackend(KeyValueStoreBackendBase):
    connector_klass = RedisConnector

    def _check_connection(self):
        if not self.connector.is_connected():
            raise ConnectionError

    def insert_record(self, schema_name: str, record_key: str, record: object):
        self._check_connection()

        if self.connector.cursor.hexists(schema_name, record_key):
            raise Exception

        with self.connector.cursor.pipeline() as pipe:
            pipe.multi()
            pipe.hset(
                schema_name,
                record_key,
                pickle.dumps(record.__getstate__(), protocol=pickle.HIGHEST_PROTOCOL),
            )

            pipe.execute()

    def update_record(self, schema_name: str, record_key: str, record: object):
        self._check_connection()

        if not self.connector.cursor.hexists(schema_name, record_key):
            raise Exception

        with self.connector.cursor.pipeline() as pipe:
            pipe.hset(
                schema_name,
                record_key,
                pickle.dumps(record.__getstate__(), protocol=pickle.HIGHEST_PROTOCOL),
            )

            pipe.execute()

    def delete_record(self, schema_name, record_key):
        self._check_connection()

        if not self.connector.cursor.hexists(schema_name, record_key):
            raise Exception

        with self.connector.cursor.pipeline() as pipe:
            pipe.hdel(schema_name, record_key)
            pipe.execute()

    @staticmethod
    def load_record(record_state, record_klass: typing.Type[object]):
        record_state = pickle.loads(record_state)
        record = record_klass.__new__(record_klass)
        record.__setstate__(record_state)
        return record

    def reload_record(self, schema_name: str, record: object):
        self._check_connection()

        if not self.connector.cursor.hexists(schema_name, record.id):
            raise Exception

        state = self.connector.cursor.hget(schema_name, record.id)
        record.__setstate__(state)
