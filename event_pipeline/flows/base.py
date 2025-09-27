import typing
from pydantic_mini import BaseModel, MiniAnnotated, Attrib
from event_pipeline.mixins import ObjectIdentityMixin
from event_pipeline.runners.execution_data import ExecutionContext

if typing.TYPE_CHECKING:
    from event_pipeline.parser.protocols import TaskGroupingProtocol, TaskProtocol


class FlowBase(ObjectIdentityMixin, BaseModel):
    # The execution context for this flow
    context: ExecutionContext

    #  The profile of the tasks to be executed
    task_profiles: MiniAnnotated[
        typing.Set[typing.Union["TaskProtocol", "TaskGroupingProtocol"]],
        Attrib(default_factory=lambda: set()),
    ]

    class Config:
        disable_type_check = True

    def __model_init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def add_task_profile(self, task_profile: typing.Union["TaskProtocol", "TaskGroupingProtocol"]) -> None:
        self.task_profiles.add(task_profile)

    def get_flow_executor(self):
        raise NotImplementedError()

    def get_flow_executor_config(self):
        raise NotImplementedError()

    async def run(self) -> None:
        raise NotImplementedError()

    @classmethod
    def setup_next_flow(cls, next_flow: "FlowBase", previous: typing.Optional["FlowBase"]=None) -> None:
        pass
