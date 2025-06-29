import typing
from enum import Enum


class ConfigState(Enum):
    """Configuration state indicators"""
    UNSET = "unset"


T = typing.TypeVar('T')
ConfigurableValue = typing.Union[T, None, ConfigState]
