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

    def get_event_name(self) -> str:
        if isinstance(self.event, str):
            return self.event
        return self.event.__name__

    def get_dot_node_data(self) -> str:
        if self.is_sink:
            return f'\t"{self.id}" [label="{self.get_event_name()}", shape=box, style="filled,rounded", fillcolor=yellow]\n'
        elif self.is_conditional:
            return f'\t"{self.id}" [label="{self.get_event_name()}", shape=diamond, style="filled,rounded", fillcolor=yellow]\n'
        elif self.is_parallel_execution_node:
            nodes = self.get_parallel_nodes()
            node_id = nodes[0].get_id()
            node_label = "{" + "|".join([n.get_event_name() for n in nodes]) + "}"
            return f'\t"{node_id}" [label="{node_label}", shape=record, style="filled,rounded", fillcolor=lightblue]\n'

        return f'\t"{self.id}" [label="{self.get_event_name()}", shape=circle, style="filled,rounded", fillcolor=yellow]\n'


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

    def get_event_name(self) -> str:
        return "TaskGrouping"

    def get_dot_node_data(self) -> str:
        from event_pipeline.translator.dot import draw_subgraph_from_task_state

        return draw_subgraph_from_task_state(self)
