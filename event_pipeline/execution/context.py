import typing
import time
import logging
import asyncio
from collections import deque
from pydantic_mini import BaseModel, MiniAnnotated, Attrib
from pydantic_mini.exceptions import ValidationError as PydanticMiniError
from dataclasses import dataclass, field
from event_pipeline.pipeline import Pipeline
from event_pipeline.mixins import ObjectIdentityMixin
from event_pipeline.result import ResultSet, EventResult
from event_pipeline.signal.signals import (
    event_execution_aborted,
    event_execution_cancelled,
    event_execution_failed,
)
from event_pipeline.parser.operator import PipeType
from event_pipeline.typing import TaskType
from event_pipeline.result_evaluators import EventEvaluator, ResultEvaluationStrategies
from event_pipeline.parser.protocols import TaskProtocol, TaskGroupingProtocol

if typing.TYPE_CHECKING:
    from .state_manager import StateManager, ExecutionState, ExecutionStatus

logger = logging.getLogger(__name__)


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

    @property
    async def state_async(self) -> ExecutionState:
        """
        Async version of getting current state from shared memory.
        """
        return await self._state_manager.get_state_async(self.state_id)

    def update_status(self, new_status: ExecutionStatus) -> None:
        self._state_manager.update_status(self.state_id, new_status)

    async def update_status_async(self, new_status: ExecutionStatus) -> None:
        await self._state_manager.update_status_async(self.state_id, new_status)

    def add_error(self, error: Exception) -> None:
        self._state_manager.append_error(self.state_id, error)

    async def add_error_async(self, error: Exception) -> None:
        await self._state_manager.append_error_async(self.state_id, error)

    def add_result(self, result: EventResult) -> None:
        self._state_manager.append_result(self.state_id, result)

    async def add_result_async(self, result: EventResult) -> None:
        await self._state_manager.append_result_async(self.state_id, result)

    def cancel(self) -> None:
        """
        Cancel execution - only locks THIS context.
        Other contexts continue running unaffected.
        """
        self._state_manager.update_status(self.state_id, ExecutionStatus.CANCELLED)
        # Emit event
        event_execution_cancelled.emit(
            sender=self.__class__,
            task_profiles=self.get_task_profiles().copy(),
            execution_context=self,
            state=ExecutionStatus.CANCELLED,
        )

    async def cancel_async(self) -> None:
        """
        Async version of cancel execution - only locks THIS context.
        Other contexts continue running unaffected.
        """
        await self._state_manager.update_status_async(
            self.state_id, ExecutionStatus.CANCELLED
        )
        # Emit event
        await event_execution_cancelled.emit_async(
            sender=self.__class__,
            task_profiles=self.get_task_profiles().copy(),
            execution_context=self,
            state=ExecutionStatus.CANCELLED,
        )

    def abort(self) -> None:
        """
        Abort execution - only locks THIS context.
        Other contexts continue running unaffected.
        """
        self._state_manager.update_status(self.state_id, ExecutionStatus.ABORTED)
        # Emit event
        event_execution_aborted.emit(
            sender=self.__class__,
            task_profiles=self.get_task_profiles().copy(),
            execution_context=self,
            state=ExecutionStatus.ABORTED,
        )

    async def abort_async(self) -> None:
        """
        Async version of abort execution - only locks THIS context.
        Other contexts continue running unaffected.
        """
        await self._state_manager.update_status_async(
            self.state_id, ExecutionStatus.ABORTED
        )
        # Emit event
        await event_execution_aborted.emit_async(
            sender=self.__class__,
            task_profiles=self.get_task_profiles().copy(),
            execution_context=self,
            state=ExecutionStatus.ABORTED,
        )

    def failed(self):
        """
        Mark the execution context as failed.
        """
        self._state_manager.update_status(self.state_id, ExecutionStatus.FAILED)
        # Emit event
        event_execution_failed.emit(
            sender=self.__class__,
            task_profiles=self.get_task_profiles().copy(),
            execution_context=self,
            state=ExecutionStatus.FAILED,
        )

    async def failed_async(self):
        """
        Async version of marking the execution context as failed.
        """
        await self._state_manager.update_status_async(
            self.state_id, ExecutionStatus.FAILED
        )
        # Emit event
        await event_execution_failed.emit_async(
            sender=self.__class__,
            task_profiles=self.get_task_profiles().copy(),
            execution_context=self,
            state=ExecutionStatus.FAILED,
        )

    def get_state_snapshot(self) -> ExecutionState:
        """Get a thread-safe copy of current state."""
        return self.state

    def bulk_update(
        self,
        status: typing.Optional[ExecutionStatus] = None,
        errors: typing.Optional[typing.Sequence[Exception]] = None,
        results: typing.Optional[typing.Sequence[EventResult]] = None,
    ) -> None:
        """Efficient bulk update"""
        state = self.state
        if status is not None:
            state.status = status
        if errors is not None:
            state.errors.extend(errors)
        if results is not None:
            state.results.extend(results)
        self._state_manager.update_state(self.state_id, state)

    async def bulk_update_async(
        self,
        status: typing.Optional[ExecutionStatus] = None,
        errors: typing.Optional[typing.Sequence[Exception]] = None,
        results: typing.Optional[typing.Sequence[EventResult]] = None,
    ) -> None:
        """Async version of efficient bulk update"""
        state = await self.state_async
        if status is not None:
            state.status = status
        if errors is not None:
            state.errors.extend(errors)
        if results is not None:
            state.results.extend(results)
        await self._state_manager.update_state_async(self.state_id, state)

    def __iter__(self):
        current = self
        while current is not None:
            yield current
            current = current.next_context

    def __hash__(self):
        return hash(self.id)

    def dispatch(self, timeout: typing.Optional[float] = None):
        """
        Dispatch the task associated with this execution context.
        Args:
            timeout: Optional dispatch timeout
        Returns:
            SwitchRequest if task switching is requested, else None.
        """
        from .coordinator import ExecutionCoordinator

        coordinator = ExecutionCoordinator(execution_context=self, timeout=timeout)

        try:
            return coordinator.execute()
        except Exception as e:
            logger.error(
                f"{self.pipeline.__class__.__name__} : {str(self.task_profiles)} : {str(e)}"
            )

    def get_task_profiles(self) -> typing.Deque:
        task_profiles = self.task_profiles
        if typing.TYPE_CHECKING:
            task_profiles = typing.cast(typing.Deque, task_profiles)
        return task_profiles

    def is_multitask(self) -> bool:
        return len(self.get_task_profiles()) > 1

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

    def get_decision_task_profile(
        self,
    ) -> typing.Union["TaskProtocol", "TaskGroupingProtocol", None]:
        """
        Retrieves task profile for use in making decisions.

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
        task_profiles = self.get_task_profiles()
        if len(task_profiles) == 1:
            return self.task_profiles[0]

        for task_profile in task_profiles:
            pointer_to_task = task_profile.get_task_pointer_type()
            if (
                pointer_to_task == PipeType.PARALLELISM
                and task_profile.condition_node.on_success_pipe != PipeType.PARALLELISM
            ):
                return task_profile
        return None

    def get_result_evaluator(self):
        """
        Retrieves the result evaluation strategy from the task profile.

        This method first identifies the relevant task profile using the
        `get_decision_task_profile` method. If a task profile is found,
        it then accesses the associated condition node to retrieve the
        result evaluation strategy.

        Returns:
            EventEvaluator: The result evaluation strategy associated with the
            task profile, or None if no task profile is found.
        """
        task_profile = self.get_decision_task_profile()
        if task_profile:
            if task_profile.options and task_profile.options.is_configured(
                "result_evaluation_strategy"
            ):
                # resolve evaluation strategy from options
                try:
                    strategy = getattr(
                        ResultEvaluationStrategies,
                        task_profile.options.result_evaluation_strategy.name,
                    )
                except AttributeError as e:
                    logger.warning(
                        f"Error resolving result evaluation strategy from options: {e}"
                    )
                    strategy = None

                if strategy:
                    return EventEvaluator(strategy=strategy)

            return task_profile.get_event_klass().evaluator()
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
