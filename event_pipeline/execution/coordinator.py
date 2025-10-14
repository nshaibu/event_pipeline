import typing
from event_pipeline.execution.context import ExecutionContext
from event_pipeline.parser.protocols import TaskProtocol, TaskGroupingProtocol


class ExecutionCoordinator:
    """Coordinates execution of tasks based on task hierarchy"""

    def __init__(self, execution_context: ExecutionContext):
        self.execution_context = execution_context
