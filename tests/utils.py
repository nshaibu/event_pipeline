import importlib


def is_package_installed(package: str) -> bool:
    try:
        importlib.import_module(package)
        return True
    except ImportError:
        return False
