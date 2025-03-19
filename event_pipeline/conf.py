import os
import typing
import logging
import importlib.util

__all__ = ["ConfigLoader"]


ENV_CONFIG = "EVENT_PIPELINE_CONFIG"

ENV_CONFIG_DIR = "EVENT_PIPELINE_CONFIG_DIR"

CONFIG_FILE = "settings.py"

logger = logging.getLogger(__name__)

_default_config = None


class ConfigLoader:
    def __init__(self, config_file=None):
        self._config = {}

        for file in self._get_config_files(config_file):
            self.load_from_file(file)

    def _get_config_files(self, config_file=None):
        file = self._search_for_config_file_in_current_directory()
        if file:
            yield file

        if ENV_CONFIG in os.environ:
            yield os.environ[ENV_CONFIG]

        if config_file:
            yield config_file

    @staticmethod
    def _search_for_config_file_in_current_directory():
        dir_path = os.environ.get(ENV_CONFIG_DIR, ".")
        for root, dirs, files in os.walk(dir_path):
            if CONFIG_FILE in files:
                return os.path.join(root, CONFIG_FILE)

    def load_from_file(self, config_file: typing.Union[str, os.PathLike]):
        """Load configurations from a Python config file."""
        if not os.path.exists(config_file):
            logger.info(
                f"Config file {config_file} does not exist. Skipping loading from file."
            )
            return

        # Load the config file as a Python module
        spec = importlib.util.spec_from_file_location("settings", config_file)
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)

        for field_name in dir(config_module):
            if not field_name.startswith("__") and not callable(getattr(config_module, field_name)):
                self._config[field_name.upper()] = getattr(config_module, field_name)

    def get(self, key, default=None):
        """Get the configuration value, with an optional default."""
        value = self._config.get(key, default)
        if value is None:
            value = os.environ.get(key)
        if value is None:
            raise AttributeError(f"Missing configuration key '{key}'")
        return value

    def __getattribute__(self, item):
        try:
            value = super().__getattribute__(item)
        except AttributeError:
            if item != "_config" or not str(item).startswith("__"):
                return self.get(str(item).upper())
            raise
        return value

    def __repr__(self):
        return f"ConfigLoader <len={len(self._config)}>"

    @classmethod
    def get_lazily_loaded_config(cls, config_file=None):
        global _default_config
        if _default_config is None:
            _default_config = cls(config_file=config_file)
        return _default_config
