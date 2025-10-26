import typing
from enum import Enum
from event_pipeline.parser.protocols import TaskProtocol, TaskGroupingProtocol


TaskType = typing.TypeVar("TaskType", TaskProtocol, TaskGroupingProtocol)


class ConfigState(Enum):
    """Configuration state indicators"""

    UNSET = "unset"


T = typing.TypeVar("T")
ConfigurableValue = typing.Union[T, None, ConfigState]
