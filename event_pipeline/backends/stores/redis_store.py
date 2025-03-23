import typing
import pickle
from pydantic_mini import BaseModel
from event_pipeline.backends.connectors.redis import RedisConnector
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.exceptions import ObjectDoesNotExist, ObjectExistError


class RedisStoreBackend(KeyValueStoreBackendBase):
    connector_klass = RedisConnector

    def _check_connection(self):
        if not self.connector.is_connected():
            raise ConnectionError("Redis is not connected.")

    @staticmethod
    def _generate_filter_match(**filter_kwargs):
        def match_record(record):
            for key, value in filter_kwargs.items():
                if not hasattr(record, key) or getattr(record, key) != value:
                    return False
            return True

        return match_record

    def exists(self, schema_name: str, record_key: str) -> bool:
        self._check_connection()
        return self.connector.cursor.hexists(schema_name, record_key)

    def count(self, schema_name: str) -> int:
        self._check_connection()
        return self.connector.cursor.hlen(schema_name)

    def insert_record(self, schema_name: str, record_key: str, record: BaseModel):
        if self.exists(schema_name, record_key):
            raise ObjectExistError(
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

    def update_record(self, schema_name: str, record_key: str, record: BaseModel):
        if not self.exists(schema_name, record_key):
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
        if not self.exists(schema_name, record_key):
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

        with self.connector.cursor.pipeline() as pipe:
            pipe.hdel(schema_name, record_key)
            pipe.execute()

    @staticmethod
    def load_record(record_state, record_klass: typing.Type[BaseModel]):
        record_state = pickle.loads(record_state)
        record = record_klass.__new__(record_klass)
        record.__setstate__(record_state)
        return record

    def reload_record(self, schema_name: str, record: BaseModel):
        if not self.exists(schema_name, record.id):
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

        state = self.connector.cursor.hget(schema_name, record.id)
        record_state = pickle.loads(state)
        record.__setstate__(record_state)

    def get_record(
        self,
        schema_name: str,
        klass: typing.Type[BaseModel],
        record_key: typing.Union[str, int],
    ) -> BaseModel:
        if not self.exists(schema_name, record_key):
            raise ObjectDoesNotExist(
                "Record does not exist in schema '{}'".format(schema_name)
            )

        state = self.connector.cursor.hget(schema_name, record_key)
        record = self.load_record(state, klass)
        return record

    def filter_record(
        self,
        schema_name: str,
        record_klass: typing.Type[BaseModel],
        **filter_kwargs,
    ):
        self._check_connection()

        match_func = self._generate_filter_match(**filter_kwargs)

        matching_records = []
        cursor = 0
        while True:
            cursor, data = self.connector.cursor.hscan(schema_name, cursor=cursor)

            for key, value in data.items():
                record = self.load_record(value, record_klass)
                if match_func(record):
                    matching_records.append(record)

            if cursor == 0:
                break

        return matching_records
