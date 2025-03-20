import os
import typing
import logging
import threading
import importlib.util
from event_pipeline import settings as default_settings

__all__ = ["ConfigLoader"]


ENV_CONFIG = "EVENT_PIPELINE_CONFIG"

ENV_CONFIG_DIR = "EVENT_PIPELINE_CONFIG_DIR"

CONFIG_FILE = "settings.py"

logger = logging.getLogger(__name__)

_default_config = None
_config_lock = threading.Lock()


class ConfigLoader:
    def __init__(self, config_file=None):
        self._config = {}

        self._load_module(default_settings)

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
        # Check the specified directory first
        config_path = os.path.join(dir_path, CONFIG_FILE)
        if os.path.isfile(config_path):
            return config_path

        # Check immediate subdirectories only (one level deep)
        try:
            for item in os.listdir(dir_path):
                subdir = os.path.join(dir_path, item)
                if os.path.isdir(subdir):
                    config_path = os.path.join(subdir, CONFIG_FILE)
                    if os.path.isfile(config_path):
                        return config_path
        except (PermissionError, FileNotFoundError) as e:
            logger.debug(f"Error scanning directories: {e}")

        return None

    def _load_module(self, config_module):
        for field_name in dir(config_module):
            if not field_name.startswith("__") and not callable(
                getattr(config_module, field_name)
            ):
                self._config[field_name.upper()] = getattr(config_module, field_name)

    def load_from_file(self, config_file: typing.Union[str, os.PathLike]):
        """Load configurations from a Python config file."""
        if not os.path.exists(config_file):
            logger.info(
                f"Config file {config_file} does not exist. Skipping loading from file."
            )
            return

        try:
            # Load the config file as a Python module
            spec = importlib.util.spec_from_file_location("settings", config_file)
            if spec is None:
                logger.warning(f"Could not load spec for {config_file}")
                return

            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)

            self._load_module(config_module)
        except ModuleNotFoundError:
            logger.error(f"Config file {config_file} could not be loaded.")

    def get(self, key, default=None):
        """Get the configuration value, with an optional default."""
        value = self._config.get(key, default)
        if value is None:
            value = os.environ.get(key)
        if value is None:
            raise AttributeError(f"Missing configuration key '{key}'")
        return value

    def __getattr__(self, item):
        """Handle attribute access for configuration keys."""
        if item.startswith("_"):
            # Let Python handle private attributes normally
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{item}'"
            )

        # Look up using uppercase key
        return self.get(item.upper())

    def __repr__(self):
        return f"ConfigLoader <len={len(self._config)}>"

    @classmethod
    def get_lazily_loaded_config(cls, config_file=None):
        global _default_config

        if _default_config is not None:
            return _default_config

        with _config_lock:
            if _default_config is None:
                _default_config = cls(config_file=config_file)
        return _default_config
