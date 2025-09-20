import typing
import time
from enum import Enum
from dataclasses import dataclass, field

from event_pipeline.mixins import ObjectIdentityMixin
from event_pipeline.result import ResultSet, EventResult
from event_pipeline.exceptions import PipelineError
from event_pipeline.signal.signals import (
    event_execution_aborted,
    event_execution_cancelled,
)

if typing.TYPE_CHECKING:
    from event_pipeline.pipeline import Pipeline
    from event_pipeline.parser.protocols import TaskProtocol, TaskGroupingProtocol


class ExecutionStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    CANCELLED = "cancelled"
    FINISHED = "finished"
    ABORTED = "aborted"


@dataclass
class ExecutionMetrics:
    """Execution timing and statistics"""

    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0.0


@dataclass
class ExecutionState:
    """Execution state"""

    status: ExecutionStatus = field(default=ExecutionStatus.PENDING)
    errors: typing.List[PipelineError] = field(default_factory=list)
    results: ResultSet[EventResult] = field(default_factory=lambda: ResultSet([]))

    def cancel(self, execution_context: "ExecutionContext") -> None:
        """
        Cancels the execution context. This method must acquire
        the lock before executing it.
        """
        self.status = ExecutionStatus.CANCELLED
        event_execution_cancelled.emit(
            sender=execution_context.__class__,
            task_profiles=execution_context.task_profiles,
            execution_context=self,
            state=self,
        )

    def abort(self, execution_context: "ExecutionContext") -> None:
        """
        Aborts the execution context. This method must acquire the lock before executing it.
        """
        self.status = ExecutionStatus.ABORTED
        event_execution_aborted.emit(
            sender=execution_context.__class__,
            task_profiles=execution_context.task_profiles,
            execution_context=self,
            state=self,
        )


@dataclass
class ExecutionContext(ObjectIdentityMixin):
    """
    Represents the execution context for a particular event in the pipeline.

    This class encapsulates the necessary data and state associated with
    executing an event, such as the task being processed and the pipeline
    it belongs to.

    Individual events executing concurrently must acquire the "conditional_variable"
    before they can make any changes to the execution context. This ensures that only one
    event can modify the context at a time, preventing race conditions and ensuring thread safety.

    Attributes:
        task_profiles: The specific PipelineTask that is being executed.
        pipeline: The Pipeline that orchestrates the execution of the task.
        state: State of the execution of task.

    Details:
        Represents the execution context of the pipeline as a bidirectional (doubly-linked) list.
        Each node corresponds to an event's execution context, allowing traversal both forward and backward
        through the pipeline's events.

        You can filter contexts by event name using the `filter_by_event` method.

        The context is iterable in the forward direction, so you can loop through it like this:
            for context in pipeline.start():
                pass

        To access specific ends of the context queue:
        - Use `get_execution_context_head()` to retrieve the head (starting context).
        - Use `get_tail_context()` to retrieve the tail (ending context).

        Reverse traversal can be done by walking backward from the tail using the linked structure.
    """

    task_profiles: typing.List[typing.Union["TaskProtocol", "TaskGroupingProtocol"]]
    pipeline: "Pipeline"
    state: ExecutionState = field(
        default_factory=lambda: ExecutionState(ExecutionStatus.PENDING)
    )
    metrics: ExecutionMetrics = field(default_factory=lambda: ExecutionMetrics())
    previous_context: typing.Optional["ExecutionContext"] = None
    next_context: typing.Optional["ExecutionContext"] = None

    def __post_init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __iter__(self):
        current = self
        while current is not None:
            yield current
            current = current.next_context

    def __hash__(self):
        return hash(self.id)

    def is_multitask(self) -> bool:
        return len(self.task_profiles) > 1

    def get_execution_context_head(self) -> "ExecutionContext":
        """
        Returns the execution context head of the execution context.
        :return: ExecutionContext head of the execution context.
        """
        current = self
        while current.previous_context:
            current = current.previous_context
        return current

    def get_latest_context(self) -> "ExecutionContext":
        """
        Returns the latest execution context.
        :return: ExecutionContext
        """
        current = self.get_execution_context_head()
        while current.next_context:
            current = current.next_context
        return current

    def get_tail_context(self) -> "ExecutionContext":
        """
        Returns the tail context of the execution context.
        :return: ExecutionContext
        """
        return self.get_latest_context()

    def filter_by_event(self, event_name: str) -> ResultSet:
        """
        Filters the execution context based on the event name.
        :param event_name: Case-insensitive event name.
        :return: ResultSet with the filtered execution context.
        """
        head = self.get_execution_context_head()
        event = ""  # PipelineTask.resolve_event_name(event_name)
        result = ResultSet([])

        def filter_condition(context: ExecutionContext, term: str) -> bool:
            task_profiles = context.task_profiles

        for context in head:
            if event in [task.event for task in context.task_profiles]:
                result.add(context)
        return result

    def get_state(self) -> typing.Dict[str, typing.Any]:
        return self.__dict__

    def set_state(self, state: typing.Dict[str, typing.Any]):
        self.__dict__.update(state)
