import pytest
from nexus.backends.connectors.dummy import DummyConnector


@pytest.fixture
def dummy_connector():
    return DummyConnector()


def test_connect(dummy_connector):
    cursor = dummy_connector.connect()
    assert cursor is not None
    assert isinstance(cursor, object)


def test_disconnect(dummy_connector):
    result = dummy_connector.disconnect()
    assert result is True


def test_is_connected(dummy_connector):
    result = dummy_connector.is_connected()
    assert result is True
