import typing
import time
from collections import deque
from pydantic_mini import BaseModel, MiniAnnotated, Attrib
from pydantic_mini.exceptions import ValidationError as PydanticMiniError
from contextlib import contextmanager
from dataclasses import dataclass, field
from event_pipeline.pipeline import Pipeline
from event_pipeline.mixins import ObjectIdentityMixin
from event_pipeline.result import ResultSet, EventResult
from event_pipeline.signal.signals import (
    event_execution_aborted,
    event_execution_cancelled,
)
from event_pipeline.parser.operator import PipeType
from event_pipeline.typing import TaskType
from event_pipeline.parser.protocols import TaskProtocol, TaskGroupingProtocol

if typing.TYPE_CHECKING:
    from .state_manager import StateManager, ExecutionState, ExecutionStatus


@dataclass
class ExecutionMetrics:
    """Execution timing and statistics"""

    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0.0


def preformat_task_profile(
    task_profiles: typing.Union[
        TaskType, typing.List[TaskType], typing.Deque[TaskType]
    ],
) -> typing.Deque[TaskType]:
    if isinstance(task_profiles, (TaskProtocol, TaskGroupingProtocol)):
        return deque([task_profiles])
    elif isinstance(task_profiles, (list, tuple)):
        return deque(task_profiles)
    elif isinstance(task_profiles, deque):
        return task_profiles
    # TODO: descriptive error message
    raise PydanticMiniError("invalid task format")


class ExecutionContext(ObjectIdentityMixin, BaseModel):
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

    Details:
        Represents the execution context of the pipeline as a bidirectional (doubly-linked) list.
        Each node corresponds to an event's execution context, allowing traversal both forward and backward
        through the pipeline's events.

        You can filter contexts by event name using the `filter_by_event` method.

        The context is iterable in the forward direction, so you can loop through it like this:
            for context in pipeline.start():
                pass

        To access specific ends of the context queue:
        - Use `get_head_context()` to retrieve the head (starting context).
        - Use `get_tail_context()` to retrieve the tail (ending context).

        Reverse traversal can be done by walking backward from the tail using the linked structure.
    """

    task_profiles: MiniAnnotated[
        typing.Deque[typing.Union["TaskProtocol", "TaskGroupingProtocol"]],
        Attrib(pre_formatter=preformat_task_profile),
    ]
    pipeline: Pipeline
    metrics: ExecutionMetrics = field(default_factory=lambda: ExecutionMetrics())
    previous_context: typing.Optional["ExecutionContext"] = None
    next_context: typing.Optional["ExecutionContext"] = None

    _state_manager: typing.ClassVar[typing.Optional["StateManager"]] = None

    class Config:
        disable_type_check = True
        disable_all_validations = True

    def __model_init__(self, *args, **kwargs):
        from .state_manager import StateManager

        super().__init__(*args, **kwargs)

        # Initialize shared state manager
        if self.__class__._state_manager is None:
            self.__class__._state_manager = StateManager()

        # Create state in shared memory with its own lock
        initial_state = ExecutionState(ExecutionStatus.PENDING)
        self._state_manager.create_state(self.state_id, initial_state)

    @property
    def state_id(self) -> str:
        return self.id

    @property
    def state(self) -> ExecutionState:
        """
        Get current state from shared memory.
        """
        return self._state_manager.get_state(self.state_id)

    @contextmanager
    def lock(self):
        """
        Acquire lock for THIS context only.
        Other contexts run in parallel without blocking.
        """
        with self._state_manager.acquire(self.state_id):
            yield

    def update_status(self, new_status: ExecutionStatus) -> None:
        with self.lock():
            self._state_manager.update_status(self.state_id, new_status)

    def add_error(self, error: Exception) -> None:
        with self.lock():
            self._state_manager.append_error(self.state_id, error)

    def add_result(self, result: EventResult) -> None:
        with self.lock():
            self._state_manager.append_result(self.state_id, result)

    def cancel(self) -> None:
        """
        Cancel execution - only locks THIS context.
        Other contexts continue running unaffected.
        """
        with self.lock():
            self._state_manager.update_status(self.state_id, ExecutionStatus.CANCELLED)
            # Emit event
            event_execution_cancelled.emit(
                sender=self.__class__,
                task_profiles=self.task_profiles.copy(),
                execution_context=self,
                state=ExecutionStatus.CANCELLED,
            )

    def abort(self) -> None:
        """
        Abort execution - only locks THIS context.
        Other contexts continue running unaffected.
        """
        with self.lock():
            self._state_manager.update_status(self.state_id, ExecutionStatus.ABORTED)
            # Emit event
            event_execution_aborted.emit(
                sender=self.__class__,
                task_profiles=self.task_profiles.copy(),
                execution_context=self,
                state=ExecutionStatus.ABORTED,
            )

    def get_state_snapshot(self) -> ExecutionState:
        """Get a thread-safe copy of current state."""
        with self.lock():
            return self.state

    def bulk_update(
        self,
        status: typing.Optional[ExecutionStatus] = None,
        errors: typing.Optional[typing.List[Exception]] = None,
        results: typing.Optional[typing.List[EventResult]] = None,
    ) -> None:
        """Efficient bulk update"""
        with self.lock():
            state = self.state
            if status is not None:
                state.status = status
            if errors is not None:
                state.errors.extend(errors)
            if results is not None:
                (
                    state.results.extend(results)
                    if isinstance(state.results, list)
                    else None
                )
            self._state_manager.update_state(self.state_id, state)

    def __iter__(self):
        current = self
        while current is not None:
            yield current
            current = current.next_context

    def __hash__(self):
        return hash(self.id)

    def is_multitask(self) -> bool:
        return len(self.task_profiles) > 1

    def get_head_context(self) -> "ExecutionContext":
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
        current = self.get_head_context()
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
        head = self.get_head_context()
        event = ""  # PipelineTask.resolve_event_name(event_name)
        result = ResultSet()

        def filter_condition(context: ExecutionContext, term: str) -> bool:
            task_profiles = context.task_profiles

        for context in head:
            if event in [task.event for task in context.task_profiles]:
                result.add(context)
        return result

    def get_last_task_in_task_profile_chain(
        self,
    ) -> typing.Union["TaskProtocol", "TaskGroupingProtocol", None]:
        """
        Retrieves the last task profile in the chain of task profiles.

        This method examines the list of task profiles to identify the last task in
        a pipeline. If there is only one task profile, it returns that profile directly.
        For multiple task profiles, it iterates through each profile and checks the
        pointer type associated with the event.

        Specifically, it looks for a task profile whose pointer type indicates parallelism
        (PipeType.PARALLELISM) and ensures that its on-success pipe type is not parallelism.

        This helps in identifying the last task in a sequence when tasks are executed in parallel
        followed by a task that depends on the success of those parallel tasks.

        Returns:
            PipelineTask: The last task profile in the chain or the single task profile
                           if only one exists.
        """
        if len(self.task_profiles) == 1:
            return self.task_profiles[0]

        for task_profile in self.task_profiles:
            pointer_to_task = task_profile.get_task_pointer_type()
            if (
                pointer_to_task == PipeType.PARALLELISM
                and task_profile.condition_node.on_success_pipe != PipeType.PARALLELISM
            ):
                return task_profile
        return None

    def cleanup(self):
        """Clean up shared memory resources"""
        self._state_manager.release_state(self.state_id)

    def __del__(self):
        """Ensure cleanup on garbage collection"""
        try:
            if hasattr(self, "state_id") and self.state_id:
                self._state_manager.release_state(self.state_id)
        except:
            pass  # Ignore errors during cleanup
