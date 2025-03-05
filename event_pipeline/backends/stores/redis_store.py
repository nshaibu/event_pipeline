import typing
import pickle
from event_pipeline.backends.connectors.redis import RedisConnector
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.exceptions import ObjectDoesNotExist

if typing.TYPE_CHECKING:
    from event_pipeline.mixins.schema import SchemaMixin


class RedisStoreBackend(KeyValueStoreBackendBase):
    connector_klass = RedisConnector

    def _check_connection(self):
        if not self.connector.is_connected():
            raise ConnectionError

    def insert_record(self, schema_name: str, record_key: str, record: "SchemaMixin"):
        self._check_connection()

        if self.connector.cursor.hexists(schema_name, record_key):
            raise ObjectDoesNotExist(
                "Record already exists in schema '{}'".format(schema_name)
            )

        with self.connector.cursor.pipeline() as pipe:
            pipe.multi()
            pipe.hset(
                schema_name,
                record_key,
                pickle.dumps(record.__getstate__(), protocol=pickle.HIGHEST_PROTOCOL),
            )

            pipe.execute()

    def update_record(self, schema_name: str, record_key: str, record: "SchemaMixin"):
        self._check_connection()

        if not self.connector.cursor.hexists(schema_name, record_key):
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

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
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

        with self.connector.cursor.pipeline() as pipe:
            pipe.hdel(schema_name, record_key)
            pipe.execute()

    @staticmethod
    def load_record(record_state, record_klass: typing.Type["SchemaMixin"]):
        record_state = pickle.loads(record_state)
        record = record_klass.__new__(record_klass)
        record.__setstate__(record_state)
        return record

    def reload_record(self, schema_name: str, record: "SchemaMixin"):
        self._check_connection()

        if not self.connector.cursor.hexists(schema_name, record.id):
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

        state = self.connector.cursor.hget(schema_name, record.id)
        record.__setstate__(state)

    def get_record(
        self,
        schema_name: str,
        klass: typing.Type["SchemaMixin"],
        record_key: typing.Union[str, int],
    ) -> "SchemaMixin":
        self._check_connection()
        if not self.connector.cursor.hexists(schema_name, record_key):
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

        state = self.connector.cursor.hget(schema_name, record_key)
        record = self.load_record(state, klass)
        return record
