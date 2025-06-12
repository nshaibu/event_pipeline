import pickle
import typing
import psycopg
from pydantic_mini import BaseModel

from event_pipeline.backends.connectors.postgres import PostgresConnector
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.backends.stores.sql_utils import build_filter_params, map_types
from event_pipeline.exceptions import ObjectDoesNotExist, ObjectExistError, SqlOperationError


class PostgresStoreBackend(KeyValueStoreBackendBase):
    connector_klass = PostgresConnector

    def _check_connection(self):
        if not self.connector.is_connected():
            raise ConnectionError("PostgreSQL is not connected.")

    def _check_if_schema_exists(self, schema_name: str) -> bool:
        self._check_connection()
        try:
            self.connector.cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (schema_name.lower(),)
            )
            return self.connector.cursor.fetchone() is not None
        except psycopg.Error:
            return False

    def create_schema(self, schema_name: str, record: BaseModel):
        self._check_connection()

        if self._check_if_schema_exists(schema_name):
            raise ObjectExistError(f"Schema '{schema_name}' already exists.")

        fields = []
        for field_name, field_type in record.__annotations__.items():
            sql_type = map_types(field_type)

            field_def = f"{field_name} {sql_type}"

            fields.append(field_def)

        fields_str = ", ".join(fields)
        try:
            create_table_sql = f"""
                CREATE TABLE {schema_name} (
                    id TEXT PRIMARY KEY,
                    {fields_str}
                )
            """
            self.connector.cursor.execute(create_table_sql)
            self.connector.cursor.connection.commit()
        except psycopg.Error as e:
            raise SqlOperationError(f"Error creating schema '{schema_name}': {str(e)}")

    def exists(self, schema_name: str, record_key: str) -> bool:
        self._check_connection()
        try:
            self.connector.cursor.execute(
                f"SELECT 1 FROM {schema_name} WHERE id = %s LIMIT 1",
                (record_key,)
            )
            return self.connector.cursor.fetchone() is not None
        except psycopg.Error:
            return False

    def insert_record(self, schema_name: str, record_key: str, record: BaseModel):
        self._check_connection()
        try:
            if not self._check_if_schema_exists(schema_name):
                self.create_schema(schema_name, record)

            if self.exists(schema_name, record_key):
                raise ObjectExistError(
                    f"Record with id {record_key} already exists in table '{schema_name}'"
                )

            record_data = record.__dict__.copy()
            record_data.pop("_id", None)  # remove _id field from record_data since it would be represented by id
            record_data.pop("_backend", None)
            record_data['id'] = record_key

            fields = list(record_data.keys())
            placeholders = ['%s' for _ in fields]
            values = [str(record_data[field]) if type(record_data[field]) == dict
                      else record_data[field] for field in fields]

            insert_sql = f"""INSERT INTO {schema_name.lower()} ({', '.join(fields)}) VALUES ({', '.join(placeholders)}) """

            self.connector.cursor.execute(insert_sql, values)
            self.connector.cursor.connection.commit()
        except psycopg.Error as e:
            raise SqlOperationError(f"Error inserting record: {str(e)}")

    def update_record(self, schema_name: str, record_key: str, record: BaseModel):
        self._check_connection()
        try:
            record_data = record.__dict__.copy()
            record_data['id'] = record_key
            record_data.pop("_id", None)  # remove _id field from record_data since it would be represented by id
            record_data.pop("_backend", None)

            fields = list(record_data.keys())
            update_set = [f"{field} = %s" for field in fields if field != 'id']
            values = [str(record_data[field]) if type(record_data[field]) == dict
                      else record_data[field] for field in fields if field != 'id']
            values.append(record_key)

            update_sql = f"""
                UPDATE {schema_name.lower()}
                SET {', '.join(update_set)}
                WHERE id = %s
            """
            self.connector.cursor.execute(update_sql, values)
            if self.connector.cursor.rowcount == 0:
                raise ObjectDoesNotExist(f"Record with id {record_key} does not exist")
            self.connector.cursor.connection.commit()
        except psycopg.Error as e:
            raise SqlOperationError(f"Error updating record: {str(e)}")

    def delete_record(self, schema_name: str, record_key: str):
        self._check_connection()
        try:
            self.connector.cursor.execute(
                f"DELETE FROM {schema_name.lower()} WHERE id = %s",
                (record_key,)
            )
            if self.connector.cursor.rowcount == 0:
                raise ObjectDoesNotExist(f"Record with id {record_key} does not exist")
            self.connector.cursor.connection.commit()
        except psycopg.Error as e:
            raise SqlOperationError(f"Error deleting record: {str(e)}")

    @staticmethod
    def load_record(record_state, record_klass: typing.Type[BaseModel]):
        record_state = pickle.loads(record_state)
        record = record_klass.__new__(record_klass)
        record.__setstate__(record_state)
        return record

    def get_record(self, schema_name: str, klass: typing.Type[BaseModel], record_key: str) -> BaseModel:
        self._check_connection()
        try:
            self.connector.cursor.execute(
                f"SELECT record_state FROM {schema_name.lower()} WHERE id = %s",
                (record_key,)
            )
            row = self.connector.cursor.fetchone()
            if row is None:
                raise ObjectDoesNotExist(
                    f"Record with key {record_key} does not exist in schema '{schema_name}'"
                )
            return self.load_record(row[0], klass)
        except psycopg.Error as e:
            raise SqlOperationError(f"Error getting record: {str(e)}")

    def reload_record(self, schema_name: str, record: BaseModel):
        self._check_connection()
        try:
            self.connector.cursor.execute(
                f"SELECT record_state FROM {schema_name.lower()} WHERE id = %s",
                (record.id,)
            )
            row = self.connector.cursor.fetchone()
            if row is None:
                raise ObjectDoesNotExist(
                    f"Record with id {record.id} does not exist in schema '{schema_name}'"
                )
            record.__setstate__(pickle.loads(row[0]))
        except psycopg.Error as e:
            raise SqlOperationError(f"Error reloading record: {str(e)}")

    def count(self, schema_name: str) -> int:
        self._check_connection()
        try:
            if not self._check_if_schema_exists(schema_name):
                raise ObjectDoesNotExist(f"Schema '{schema_name}' does not exist")

            self.connector.cursor.execute(f"SELECT COUNT(*) FROM {schema_name.lower()}")
            result = self.connector.cursor.fetchone()
            return int(result[0]) if result else 0
        except psycopg.Error as e:
            raise SqlOperationError(f"Error counting records: {str(e)}")

    def filter_record(
            self,
            schema_name: str,
            record_klass: typing.Type[BaseModel],
            **filter_kwargs
    ) -> typing.List[BaseModel]:
        self._check_connection()
        try:
            if not self._check_if_schema_exists(schema_name):
                raise ObjectDoesNotExist(f"Schema '{schema_name}' does not exist")

            parameters, conditions = build_filter_params(filter_kwargs)

            query = f"SELECT record_state FROM {schema_name.lower()}"
            if conditions:
                query += f" WHERE {' AND '.join(conditions)}"

            self.connector.cursor.execute(query, parameters)
            rows = self.connector.cursor.fetchall()

            return [self.load_record(row[0], record_klass) for row in rows]
        except psycopg.Error as e:
            raise SqlOperationError(f"Error filtering records: {str(e)}")
