import typing
import logging
from concurrent.futures import Executor

from .base import FlowBase


if typing.TYPE_CHECKING:
    from event_pipeline.parser.protocols import TaskProtocol


logger = logging.getLogger(__name__)


class SingleFlow(FlowBase):
    """Setup for execution flow of a single event"""

    task_profile: typing.Optional[TaskProtocol] = None

    def __model_init__(self, *args, **kwargs) -> None:
        super().__model_init__(*args, **kwargs)
        self.task_profile = self.task_profiles[0]

    async def get_flow_executor(self, *args, **kwargs) -> typing.Type[Executor]:
        """
        Get the executor class for this flow.
        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.
        Returns:
            The executor class.
        """
        executor_class = await self.get_task_executor_from_options(self.task_profile)
        if executor_class is not None:
            return executor_class
        event_class = self.task_profile.get_event_class()
        return event_class.get_executor_class()

    async def get_flow_executor_config(self, **kwargs) -> typing.Dict[str, typing.Any]:
        pass

    async def run(self) -> None:
        pass
