from nexus.backends.connection import BackendConnectorBase


class DummyConnector(BackendConnectorBase):
    def __init__(self, *args, **kwargs):
        self._cursor = object()  # Simulate a cursor object

    def connect(self):
        # Simulate a connection establishment
        return self._cursor

    def disconnect(self):
        # Simulate disconnection
        return True

    def is_connected(self):
        # Simulate a check for connection status
        return True
