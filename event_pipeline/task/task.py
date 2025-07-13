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

    def get_dot_node_data(self) -> typing.Optional[str]:
        if self.is_sink:
            return f'\t"{self.id}" [label="{self.event}", shape=box, style="filled,rounded", fillcolor=yellow]\n'
        elif self.is_conditional:
            return f'\t"{self.id}" [label="{self.event}", shape=diamond, style="filled,rounded", fillcolor=yellow]\n'
        elif self.is_parallel_execution_node:
            nodes = self.get_parallel_nodes()
            if not nodes:
                return None
            node_id = nodes[0].id
            node_label = "{" + "|".join([n.event for n in nodes]) + "}"
            return f'\t"{node_id}" [label="{node_label}", shape=record, style="filled,rounded", fillcolor=lightblue]\n'

        return f'\t"{self.id}" [label="{self.event}", shape=circle, style="filled,rounded", fillcolor=yellow]\n'


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

    def get_dot_node_data(self) -> typing.Optional[str]:
        if self.is_sink:
            pass
