import unittest
from unittest.mock import MagicMock, patch

from nexus.mixins.utils.connector import (
    ConnectionMode,
    ConnectorManagerFactory,
    SingleConnectorManager,
    PooledConnectorManager,
    ConnectionStats,
)


class TestConnectorManagerFactory(unittest.TestCase):
    def test_create_manager_single_mode(self):
        mock_connector_class = MagicMock()
        connector_config = {"param": "value"}
        manager = ConnectorManagerFactory.create_manager(
            mock_connector_class,
            connector_config,
            connection_mode=ConnectionMode.SINGLE,
        )
        self.assertIsInstance(manager, SingleConnectorManager)

    def test_create_manager_pooled_mode(self):
        mock_connector_class = MagicMock()
        connector_config = {"param": "value"}
        manager = ConnectorManagerFactory.create_manager(
            mock_connector_class,
            connector_config,
            connection_mode=ConnectionMode.POOLED,
        )
        self.assertIsInstance(manager, PooledConnectorManager)

    @patch(
        "nexus.mixins.utils.connector.ConnectorManagerFactory._detect_connection_mode"
    )
    def test_create_manager_auto_detect(self, mock_detect_mode):
        mock_connector_class = MagicMock()
        connector_config = {"param": "value"}
        mock_detect_mode.return_value = ConnectionMode.POOLED
        manager = ConnectorManagerFactory.create_manager(
            mock_connector_class, connector_config
        )
        self.assertIsInstance(manager, PooledConnectorManager)
        mock_detect_mode.assert_called_once()


class TestSingleConnectorManager(unittest.TestCase):
    def setUp(self):
        self.mock_connector_class = MagicMock()
        self.connector_config = {"param": "value"}
        self.manager = SingleConnectorManager(
            self.mock_connector_class, self.connector_config
        )

    def test_get_connection_creates_new_connection(self):
        connection = self.manager.get_connection()
        self.assertIsNotNone(connection)
        self.mock_connector_class.assert_called_once_with(**self.connector_config)

    def test_get_connection_reuses_existing_connection(self):
        connection1 = self.manager.get_connection()
        connection2 = self.manager.get_connection()
        self.assertEqual(connection1, connection2)

    def test_shutdown_closes_connection(self):
        connection = self.manager.get_connection()
        self.manager.shutdown()
        self.mock_connector_class.return_value.close.assert_called_once()


class TestPooledConnectorManager(unittest.TestCase):
    def setUp(self):
        self.mock_connector_class = MagicMock()
        self.connector_config = {"param": "value"}
        self.manager = PooledConnectorManager(
            self.mock_connector_class, self.connector_config, max_connections=2
        )

    def tearDown(self):
        self.manager.shutdown()

    def test_get_connection_creates_new_connection(self):
        connection = self.manager.get_connection()
        self.assertIsNotNone(connection)
        self.mock_connector_class.assert_called_once_with(**self.connector_config)

    def test_get_connection_reuses_connection(self):
        connection1 = self.manager.get_connection()
        self.manager.release_connection(connection1)
        connection2 = self.manager.get_connection()
        self.assertEqual(connection1, connection2)

    def test_release_connection_makes_connection_available(self):
        connection = self.manager.get_connection()
        self.manager.release_connection(connection)
        self.assertIn(id(connection), self.manager._available_connections)

    def test_shutdown_closes_all_connections(self):
        connection1 = self.manager.get_connection()
        connection2 = self.manager.get_connection()
        self.manager.shutdown()
        self.mock_connector_class.return_value.close.assert_any_call()
