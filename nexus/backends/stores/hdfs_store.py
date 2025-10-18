import typing
import json
import os
from io import BytesIO
from pydantic_mini import BaseModel

from nexus.exceptions import ObjectDoesNotExist, ObjectExistError
from nexus.backends.store import KeyValueStoreBackendBase
from nexus.backends.connectors.hdfs_connector import HDFSConnector


class HDFSStoreBackend(KeyValueStoreBackendBase):
    """HDFS implementation of the key-value store backend."""

    connector_klass = HDFSConnector

    def __init__(self, **connector_config):
        super().__init__(**connector_config)
        self.base_path = connector_config.get("base_path", "/nexus")

    def _get_schema_path(self, schema_name: str) -> str:
        """Get the full HDFS path for a schema."""
        return os.path.join(self.base_path, schema_name)

    def _get_record_path(self, schema_name: str, record_key: str) -> str:
        """Get the full HDFS path for a record."""
        return os.path.join(self._get_schema_path(schema_name), f"{record_key}.json")

    def exists(self, schema_name: str, record_key: str) -> bool:
        """Check if a record exists."""
        try:
            return (
                self.connector.cursor.status(
                    self._get_record_path(schema_name, record_key)
                )
                is not None
            )
        except Exception:
            return False

    def count(self, schema_name: str) -> int:
        """Count records in a schema."""
        try:
            files = self.connector.cursor.list(self._get_schema_path(schema_name))
            return len([f for f in files if f.endswith(".json")])
        except Exception:
            return 0

    def insert_record(self, schema_name: str, record_key: str, record: BaseModel):
        """Insert a new record."""
        if self.exists(schema_name, record_key):
            raise ObjectExistError(f"Record already exists in schema '{schema_name}'")

        record_path = self._get_record_path(schema_name, record_key)
        schema_path = self._get_schema_path(schema_name)

        # Ensure schema directory exists
        if not self.connector.cursor.content(schema_path, strict=False):
            self.connector.cursor.makedirs(schema_path)

        # Write record data
        data = record.__getstate__()
        with BytesIO(json.dumps(data).encode("utf-8")) as bio:
            self.connector.cursor.write(record_path, bio)

    def update_record(self, schema_name: str, record_key: str, record: BaseModel):
        """Update an existing record."""
        if not self.exists(schema_name, record_key):
            raise ObjectDoesNotExist(f"Record does not exist in schema '{schema_name}'")

        record_path = self._get_record_path(schema_name, record_key)
        data = record.__getstate__()
        with BytesIO(json.dumps(data).encode("utf-8")) as bio:
            self.connector.cursor.write(record_path, bio, overwrite=True)

    def delete_record(self, schema_name: str, record_key: str):
        """Delete a record."""
        if not self.exists(schema_name, record_key):
            raise ObjectDoesNotExist(f"Record does not exist in schema '{schema_name}'")

        self.connector.cursor.delete(self._get_record_path(schema_name, record_key))

    def get_record(
        self,
        schema_name: str,
        klass: typing.Type[BaseModel],
        record_key: typing.Union[str, int],
    ) -> BaseModel:
        """Get a specific record."""
        if not self.exists(schema_name, record_key):
            raise ObjectDoesNotExist(f"Record does not exist in schema '{schema_name}'")

        record_path = self._get_record_path(schema_name, record_key)
        with self.connector.cursor.read(record_path) as reader:
            data = json.load(reader)
            return self.load_record(data, klass)

    def reload_record(self, schema_name: str, record: BaseModel):
        """Reload a record's data."""
        if not self.exists(schema_name, record.id):
            raise ObjectDoesNotExist(f"Record does not exist in schema '{schema_name}'")

        record_path = self._get_record_path(schema_name, record.id)
        with self.connector.cursor.read(record_path) as reader:
            data = json.load(reader)
            record.__setstate__(data)

    def filter_record(
        self,
        schema_name: str,
        record_klass: typing.Type[BaseModel],
        **filter_kwargs,
    ):
        """Filter records based on criteria."""
        schema_path = self._get_schema_path(schema_name)
        match_func = self._generate_filter_match(**filter_kwargs)
        matching_records = []

        try:
            files = self.connector.cursor.list(schema_path)
            for file in files:
                if not file.endswith(".json"):
                    continue

                file_path = os.path.join(schema_path, file)
                with self.connector.cursor.read(file_path) as reader:
                    data = json.load(reader)
                    record = self.load_record(data, record_klass)
                    if match_func(record):
                        matching_records.append(record)
        except Exception:
            pass

        return matching_records

    @staticmethod
    def load_record(record_state, record_klass: typing.Type[BaseModel]):
        """Load a record from its state."""
        record = record_klass.__new__(record_klass)
        record.__setstate__(record_state)
        return record
