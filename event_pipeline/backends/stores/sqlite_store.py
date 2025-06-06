import pickle
import sqlite3
import typing

from pydantic_mini import BaseModel

from event_pipeline.backends.connectors.sqlite import SqliteConnector
from event_pipeline.backends.store import KeyValueStoreBackendBase
from event_pipeline.exceptions import (
    ObjectDoesNotExist,
    SqlOperationError,
    ObjectExistError,
)


class SqliteStoreBackend(KeyValueStoreBackendBase):
    connector_klass = SqliteConnector

    def _check_if_schema_exists(self, schema_name: str) -> bool:
        self._check_connection()
        try:
            self.connector.cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (schema_name,),
            )
            return self.connector.cursor.fetchone() is not None
        except sqlite3.Error:
            return False

    def _map_types(self, field_type: typing.Any) -> str:
        from pydantic_mini.typing import get_type

        field_type = get_type(field_type)
        if field_type == bool:
            return "BOOLEAN"
        elif field_type == int:
            return "INTEGER"
        elif field_type == float:
            return "REAL"
        elif field_type == str:
            return "VARCHAR"
        elif field_type == typing.Any:
            return "JSON"

        return "JSON"

    def _convert_key_type(self, record_key: typing.Union[str, int]) -> typing.Any:
        if isinstance(record_key, str):
            try:
                return int(record_key)
            except ValueError:
                return record_key
        return record_key

    def create_schema(self, schema_name: str, record: BaseModel):
        self._check_connection()

        if self._check_if_schema_exists(schema_name):
            raise ObjectExistError(f"Schema '{schema_name}' already exists.")

        fields = []
        for field_name, field_type in record.__annotations__.items():
            sql_type = self._map_types(field_type)

            is_optional = (
                hasattr(field_type, "__class__")
                and field_type.__class__.__name__ == "_UnionType"
                and type(None) in field_type.__args__
            )

            field_def = f"{field_name} {sql_type}"
            if not is_optional:
                field_def += " NOT NULL"

            fields.append(field_def)

        fields_str = ", ".join(fields)
        try:
            create_table_sql = (
                f"CREATE TABLE {schema_name} (id VARCHAR PRIMARY KEY, {fields_str})"
            )
            self.connector.cursor.execute(create_table_sql)
            self.connector.cursor.connection.commit()
        except sqlite3.Error as e:
            raise SqlOperationError(f"Error creating schema '{schema_name}': {str(e)}")

    def _check_connection(self):
        if not self.connector.is_connected():
            raise ConnectionError("Sqlite is not connected.")

    def exists(self, schema_name: str, record_id: str) -> bool:
        self._check_connection()
        try:
            self.connector.cursor.execute(
                f"SELECT 1 FROM {schema_name} WHERE id = ? LIMIT 1",
                (record_id,),
            )
            return self.connector.cursor.fetchone() is not None
        except sqlite3.Error as e:
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
            record_data["id"] = record_key

            record_data.pop(
                "_id", None
            )  # remove _id field from record_data since it would be represented by id
            record_data.pop("_backend", None)

            fields = list(record_data.keys())
            placeholders = ["?" for _ in fields]
            values = [
                (
                    str(record_data[field])
                    if type(record_data[field]) == dict
                    else record_data[field]
                )
                for field in fields
            ]

            insert_sql = f"""
                INSERT INTO {schema_name} ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
                """
            self.connector.cursor.execute(insert_sql, values)
            self.connector.cursor.connection.commit()
        except sqlite3.Error as e:
            raise SqlOperationError(f"Error inserting record: {str(e)}")

    def update_record(self, schema_name: str, record_key: str, record: BaseModel):
        self._check_connection()
        record_key = self._convert_key_type(record_key)
        try:
            record_data = record.__dict__.copy()
            record_state = pickle.dumps(
                record.__getstate__(), protocol=pickle.HIGHEST_PROTOCOL
            )
            record_data["id"] = record_key
            record_data["record_state"] = record_state

            fields = list(record_data.keys())
            placeholders = ["?" for _ in fields]
            update_set = [f"{field} = ?" for field in fields if field != "id"]
            values = [record_data[field] for field in fields]
            update_values = [record_data[field] for field in fields if field != "id"]

            upsert_query = f"""
                                INSERT INTO {schema_name} 
                                ({', '.join(fields)}) 
                                VALUES ({', '.join(placeholders)})
                                ON CONFLICT(id) DO UPDATE SET 
                                {', '.join(update_set)}
                                WHERE id = ?
                            """
            self.connector.cursor.execute(
                upsert_query, values + update_values + [record_key]
            )
            self.connector.cursor.connection.commit()
        except sqlite3.Error as e:
            raise SqlOperationError(f"Error updating record: {str(e)}")

    def delete_record(self, schema_name: str, record_key: str):
        self._check_connection()
        record_key = self._convert_key_type(record_key)

        try:
            self.connector.cursor.execute(
                f"DELETE FROM {schema_name} WHERE id = ?", (record_key,)
            )
            if self.connector.cursor.rowcount == 0:
                raise ObjectDoesNotExist(f"Record with id {record_key} does not exist")
            self.connector.cursor.connection.commit()
        except sqlite3.Error as e:
            raise SqlOperationError(f"Error deleting record: {str(e)}")

    @staticmethod
    def load_record(record_state, record_klass: typing.Type[BaseModel]):
        record_state = pickle.loads(record_state)
        record = record_klass.__new__(record_klass)
        record.__setstate__(record_state)
        return record

    def get_record(
        self,
        schema_name: str,
        klass: typing.Type[BaseModel],
        record_key: typing.Union[str, int],
    ) -> BaseModel:
        self._check_connection()
        record_key = self._convert_key_type(record_key)

        try:
            self.connector.cursor.execute(
                f"SELECT * FROM {schema_name} WHERE id = ?", (record_key,)
            )
            row = self.connector.cursor.fetchone()
            if row is None:
                raise ObjectDoesNotExist(
                    f"Record with key {record_key} does not exist in schema '{schema_name}'"
                )
            return self.load_record(row[0], klass)
        except sqlite3.Error as e:
            raise SqlOperationError(f"Error getting record: {str(e)}")

    def reload_record(self, schema_name: str, record: BaseModel):
        self._check_connection()
        record_key = self._convert_key_type(record.id)

        try:
            self.connector.cursor.execute(
                f"SELECT record_state FROM {schema_name} WHERE id = ?", (record_key,)
            )
            row = self.connector.cursor.fetchone()
            if row is None:
                raise ObjectDoesNotExist(
                    f"Record with id {record_key} does not exist in schema '{schema_name}'"
                )
            record.__setstate__(pickle.loads(row[0]))
        except sqlite3.Error as e:
            raise SqlOperationError(f"Error reloading record: {str(e)}")

    def count(self, schema_name: str) -> int:
        self._check_connection()
        try:
            if not self._check_if_schema_exists(schema_name):
                raise ObjectDoesNotExist(f"Schema '{schema_name}' does not exist")

            self.connector.cursor.execute(f"SELECT COUNT(*) FROM {schema_name}")
            result = self.connector.cursor.fetchone()
            return int(result[0]) if result else 0
        except sqlite3.Error as e:
            raise SqlOperationError(f"Error counting records: {str(e)}")

    def _build_sql_filter(self, filter_kwargs: dict) -> typing.Tuple[str, list]:
        conditions = []
        parameters = []

        for key, value in filter_kwargs.items():
            if "__" in key:
                field, operator = key.rsplit("__", 1)
                if operator == "contains":
                    conditions.append(f"{field} LIKE ?")
                    parameters.append(f"%{value}%")
                elif operator == "startswith":
                    conditions.append(f"{field} LIKE ?")
                    parameters.append(f"{value}%")
                elif operator == "endswith":
                    conditions.append(f"{field} LIKE ?")
                    parameters.append(f"%{value}")
                elif operator == "icontains":
                    conditions.append(f"LOWER({field}) LIKE LOWER(?)")
                    parameters.append(f"%{value}%")
                elif operator in ("gt", "gte", "lt", "lte"):
                    op_map = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
                    conditions.append(f"{field} {op_map[operator]} ?")
                    parameters.append(value)
                elif operator == "in":
                    placeholders = ",".join(["?" for _ in value])
                    conditions.append(f"{field} IN ({placeholders})")
                    parameters.extend(value)
                elif operator == "isnull":
                    conditions.append(f"{field} IS {'NULL' if value else 'NOT NULL'}")
                elif operator == "exact":
                    conditions.append(f"{field} = ?")
                    parameters.append(value)
            else:
                conditions.append(f"{key} = ?")
                parameters.append(value)

            where_clause = " AND ".join(conditions) if conditions else "1"
        return where_clause, parameters

    def filter_record(
        self,
        schema_name: str,
        record_klass: typing.Type[BaseModel],
        **filter_kwargs,
    ) -> typing.List[BaseModel]:
        self._check_connection()

        try:
            if not self._check_if_schema_exists(schema_name):
                raise ObjectDoesNotExist(f"Schema '{schema_name}' does not exist")

            where_clause, parameters = self._build_sql_filter(filter_kwargs)

            query = f"SELECT * FROM {schema_name}"
            if where_clause != "1":
                query += f" WHERE {where_clause}"

            self.connector.cursor.execute(query, parameters)
            rows = self.connector.cursor.fetchall()

            results = []
            for row in rows:
                record = self.load_record(row, record_klass)
                results.append(record)

            return results

        except sqlite3.Error as e:
            raise SqlOperationError(f"Error filtering records: {str(e)}")
