import typing
from enum import Enum, auto

if typing.TYPE_CHECKING:
    from .task import TaskProtocol
    from ..options import Options


class GroupingStrategy(Enum):
    # Multiple chains executed in parallel: {A->B, C||D}
    # Results aggregated and sent to next task outside the grouping if any
    MULTIPATH_CHAINS = auto()

    # Single chain executed: {A->B}
    SINGLE_CHAIN = auto()


@typing.runtime_checkable
class TaskGroupingProtocol(typing.Protocol):
    """Task group protocol."""

    # head of each task chain
    chains: typing.List["TaskProtocol"]

    # strategy for this grouping
    strategy: GroupingStrategy

    # common configurations that will be shared by the chains
    options: Options
