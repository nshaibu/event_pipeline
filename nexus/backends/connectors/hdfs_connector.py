import hdfs
from nexus.backends.connection import BackendConnectorBase


class HDFSConnector(BackendConnectorBase):
    """HDFS connector implementation."""

    def __init__(self, host, port, username=None, password=None, db=None):
        super().__init__(
            host=host, port=port, username=username, password=password, db=db
        )
        self._client = None

    def connect(self):
        """Establish connection to HDFS."""
        if not self._cursor:
            url = f"http://{self.host}:{self.port}"
            self._client = hdfs.InsecureClient(url, user=self.username)
            self._cursor = self._client
        return self._cursor

    def disconnect(self):
        """Disconnect from HDFS."""
        if self._client:
            # HDFS client doesn't have explicit close method
            self._client = None
            self._cursor = None

    def is_connected(self) -> bool:
        """Check if connected to HDFS."""
        if self._cursor:
            try:
                # Try listing root directory to check connection
                self._cursor.list("/")
                return True
            except Exception:
                return False
        return False
