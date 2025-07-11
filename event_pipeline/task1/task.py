import typing

from .base import TaskBase
from event_pipeline.base import EventBase
from event_pipeline.parser.protocols import (
    GroupingStrategy,
    TaskProtocol,
    TaskGroupingProtocol,
)


class PipelineTask(TaskBase):

    def __init__(self, event: typing.Union[typing.Type[EventBase], str]) -> None:
        super().__init__()

        self.event = event


class PipelineTaskGrouping(TaskBase):

    def __init__(
        self, chains: typing.List[typing.Union["TaskProtocol", "TaskGroupingProtocol"]]
    ) -> None:
        super().__init__()

        self.chains = chains

        self.strategy: GroupingStrategy = (
            GroupingStrategy.MULTIPATH_CHAINS
            if len(chains) > 1
            else GroupingStrategy.SINGLE_CHAIN
        )
