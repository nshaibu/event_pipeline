import typing
import asyncio
import logging

from .base import FlowBase
from event_pipeline.executors import BaseExecutor, ProcessPoolExecutor
from event_pipeline.utils import is_multiprocessing_executor


logger = logging.getLogger(__name__)


class ParallelFlow(FlowBase):
    """Class for parallel execution flows"""

    @staticmethod
    def get_multiprocessing_executor(
        executors: typing.List[typing.Type[BaseExecutor]],
    ) -> typing.Optional[typing.Type[BaseExecutor]]:
        """Get executor that support parallel execution."""
        for executor in executors:
            if is_multiprocessing_executor(executor):
                return executor
        return None

    async def _get_executors_from_task_profiles_options(
        self,
    ) -> typing.List[typing.Type[BaseExecutor]]:
        executors = await asyncio.gather(
            *[
                self.get_task_executor_from_options(task_profile)
                for task_profile in self.task_profiles
            ],
            return_exceptions=True,
        )
        return [
            executor
            for executor in executors
            if executor is not None and issubclass(executor, BaseExecutor)
        ]

    async def get_flow_executor(self, *args, **kwargs) -> typing.Type[BaseExecutor]:
        executors = await self._get_executors_from_task_profiles_options()
        if executors:
            executor = self.get_multiprocessing_executor(executors)
            if executor:
                return executor

        for task_profile in self.task_profiles:
            event_class = task_profile.get_event_class()
            executor = event_class.get_executor_class()
            if is_multiprocessing_executor(executor):
                return executor

        logger.warning("No valid parallel executor found, using default executor")
        return ProcessPoolExecutor

    async def run(self):
        pass
