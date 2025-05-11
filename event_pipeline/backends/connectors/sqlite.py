import sqlite3

from event_pipeline.backends.connection import BackendConnectorBase


class SqliteConnector(BackendConnectorBase):
    def __init__(self, host, port, db=None):
        super().__init__(host=host, port=port, db=db)
        self._connection = sqlite3.connect(db)
        self._cursor = self._connection.cursor()

    def connect(self):
        if not self._cursor:
            self._cursor = self._connection.cursor()
        return self._cursor

    def disconnect(self):
        if self._cursor:
            self._cursor.close()
            self._cursor = None

    def is_connected(self) -> bool:
        try:
            if self._connection is not None:
                self.cursor.execute("SELECT 1")
                return True
            return False
        except (sqlite3.Error, AttributeError):
            return False
