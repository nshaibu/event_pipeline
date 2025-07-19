import typing

from event_pipeline.parser.protocols import TaskProtocol, TaskGroupingProtocol

if typing.TYPE_CHECKING:
    from .registry import ExecutorRegistry


class ExecutionPlan:
    pass


class ExecutorFactory:
    """Creates and configures executors"""

    def __init__(self, executor_registry: "ExecutorRegistry"):
        self._registry = executor_registry

    def create_execution_plan(
        self, tasks: typing.List[typing.Union[TaskProtocol, TaskGroupingProtocol]]
    ) -> ExecutionPlan:
        """Creates execution plan with proper executor assignments"""
        executor_groups = self._group_tasks_by_executor(tasks)
        return ExecutionPlan(executor_groups)

    def _group_tasks_by_executor(
        self, tasks: typing.List[typing.Union[TaskProtocol, TaskGroupingProtocol]]
    ) -> typing.Dict[ExecutorConfig, typing.List[TaskExecution]]:
        """Groups tasks by their executor requirements"""
        groups = defaultdict(list)

        for task in tasks:
            executor_config = self._get_executor_config(task)
            task_execution = self._create_task_execution(task)
            groups[executor_config].append(task_execution)

        return dict(groups)
