import abc
import typing
import logging
import time
import weakref
import multiprocessing as mp
from functools import lru_cache
from collections import deque
from dataclasses import dataclass, field
from concurrent.futures import Executor, ProcessPoolExecutor
from .result import EventResult, ResultSet
from .constants import EMPTY, MAX_RETRIES, MAX_BACKOFF, MAX_BACKOFF_FACTOR
from .executors.default_executor import DefaultExecutor
from .executors.remote_executor import RemoteExecutor
from .utils import get_function_call_args
from .conf import ConfigLoader
from .exceptions import (
    StopProcessingError,
    MaxRetryError,
    SwitchTask,
    ImproperlyConfigured,
)
from event_pipeline.signal.signals import (
    event_execution_retry,
    event_execution_retry_done,
    event_init,
    event_called,
)
from event_pipeline.parser.executor_config import ExecutorInitializerConfig
from event_pipeline.result_evaluators import (
    ExecutionResultEvaluationStrategyBase,
    ResultEvaluationStrategies,
    EventEvaluator,
)
from event_pipeline.parser.options import StopCondition
from event_pipeline.parser.options import Options

__all__ = ["EventBase", "RetryPolicy", "ExecutorInitializerConfig"]


logger = logging.getLogger(__name__)

conf = ConfigLoader.get_lazily_loaded_config()

if typing.TYPE_CHECKING:
    from event_pipeline.runners.execution_data import ExecutionContext


@dataclass
class RetryPolicy:
    max_attempts: int = field(
        init=True, default=conf.get("MAX_EVENT_RETRIES", default=MAX_RETRIES)
    )
    backoff_factor: float = field(
        init=True,
        default=conf.get("MAX_EVENT_BACKOFF_FACTOR", default=MAX_BACKOFF_FACTOR),
    )
    max_backoff: float = field(
        init=True, default=conf.get("MAX_EVENT_BACKOFF", default=MAX_BACKOFF)
    )
    retry_on_exceptions: typing.List[typing.Type[Exception]] = field(
        default_factory=list
    )


class _RetryMixin:

    retry_policy: typing.Union[
        typing.Optional[RetryPolicy], typing.Dict[str, typing.Any]
    ] = None

    def __init__(self, *args, **kwargs):
        self._retry_count = 0
        super().__init__(*args, **kwargs)

    def get_retry_policy(self) -> RetryPolicy:
        if isinstance(self.retry_policy, dict):
            self.retry_policy = RetryPolicy(**self.retry_policy)
        return self.retry_policy

    def config_retry_policy(
        self,
        max_attempts: int,
        backoff_factor: float = MAX_BACKOFF_FACTOR,
        max_backoff: float = MAX_BACKOFF,
        retry_on_exceptions: typing.Tuple[typing.Type[Exception]] = (),
    ):
        config = {
            "max_attempts": max_attempts,
            "backoff_factor": backoff_factor,
            "max_backoff": max_backoff,
            "retry_on_exceptions": [],
        }
        if retry_on_exceptions:
            retry_on_exceptions = (
                retry_on_exceptions
                if isinstance(retry_on_exceptions, (tuple, list))
                else [retry_on_exceptions]
            )
            config["retry_on_exceptions"].extend(retry_on_exceptions)

        self.retry_policy = RetryPolicy(**config)

    def get_backoff_time(self) -> float:
        if self.retry_policy is None or self._retry_count <= 1:
            return 0
        backoff_value = self.retry_policy.backoff_factor * (
            2 ** (self._retry_count - 1)
        )
        return min(backoff_value, self.retry_policy.max_backoff)

    def _sleep_for_backoff(self) -> float:
        backoff = self.get_backoff_time()
        if backoff <= 0:
            return 0
        time.sleep(backoff)
        return backoff

    def is_retryable(self, exception: Exception) -> bool:
        if self.retry_policy is None:
            return False
        exception_evaluation = not self.retry_policy.retry_on_exceptions or any(
            [
                isinstance(exception, exc)
                and exception.__class__.__name__ == exc.__name__
                for exc in self.retry_policy.retry_on_exceptions
                if exc
            ]
        )
        return isinstance(exception, Exception) and exception_evaluation

    def is_exhausted(self):
        return (
            self.retry_policy is None
            or self._retry_count >= self.retry_policy.max_attempts
        )

    def retry(
        self, func: typing.Callable, /, *args, **kwargs
    ) -> typing.Tuple[bool, typing.Any]:
        if self.retry_policy is None:
            return func(*args, **kwargs)

        exception_causing_retry = None

        while True:
            if self.is_exhausted():
                event_execution_retry_done.emit(
                    sender=self._execution_context.__class__,
                    event=self,
                    execution_context=self._execution_context,
                    task_id=self._task_id,
                    max_attempts=self.retry_policy.max_attempts,
                )

                raise MaxRetryError(
                    attempt=self._retry_count,
                    exception=exception_causing_retry,
                    reason="Retryable event is already exhausted: actual error:{reason}".format(
                        reason=str(exception_causing_retry)
                    ),
                )

            logger.info(
                "Retrying event {}, attempt {}...".format(
                    self.__class__.__name__, self._retry_count
                )
            )

            try:
                self._retry_count += 1
                return func(*args, **kwargs)
            except MaxRetryError:
                # ignore this
                break
            except Exception as exc:
                if self.is_retryable(exc):
                    if exception_causing_retry is None:
                        exception_causing_retry = exc
                    back_off = self._sleep_for_backoff()

                    event_execution_retry.emit(
                        sender=self._execution_context.__class__,
                        event=self,
                        backoff=back_off,
                        retry_count=self._retry_count,
                        max_attempts=self.retry_policy.max_attempts,
                        execution_context=self._execution_context,
                        task_id=self._task_id,
                    )
                    continue
                raise

        return False, None


class _ExecutorInitializerMixin:

    executor: typing.Type[Executor] = DefaultExecutor

    executor_config: ExecutorInitializerConfig = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.get_executor_initializer_config()

    @classmethod
    def get_executor_class(cls) -> typing.Type[Executor]:
        return cls.executor

    def get_executor_initializer_config(self) -> ExecutorInitializerConfig:
        if self.executor_config:
            if isinstance(self.executor_config, dict):
                self.executor_config = ExecutorInitializerConfig.from_dict(
                    self.executor_config
                )
        else:
            self.executor_config = ExecutorInitializerConfig()
        return self.executor_config

    def is_multiprocessing_executor(self):
        """Check if using multiprocessing or remote executor"""
        return (
            self.get_executor_class() == ProcessPoolExecutor
            or self.get_executor_class() == RemoteExecutor
        )

    def get_executor_context(
        self, ctx: typing.Optional[typing.Dict[str, typing.Any]] = None
    ) -> typing.Dict[str, typing.Any]:
        """
        Retrieves the execution context for the event's executor.

        This method determines the appropriate execution context (e.g., multiprocessing context)
        based on the executor class used for the event. If the executor is configured to use
        multiprocessing, the context is set to "spawn". Additionally, any parameters required
        for the executor's initialization are fetched and added to the context.

        The resulting context dictionary is used to configure the executor for the event execution.

        Returns:
            dict: A dictionary containing the execution context for the event's executor,
                  including any necessary parameters for initialization and multiprocessing context.

        """
        executor = self.get_executor_class()
        context = dict()
        if self.is_multiprocessing_executor():
            context["mp_context"] = mp.get_context("spawn")
        elif hasattr(executor, "get_context"):
            context["mp_context"] = executor.get_context("spawn")
        params = get_function_call_args(
            executor.__init__, self.get_executor_initializer_config()
        )
        context.update(params)
        if ctx and isinstance(ctx, dict):
            context.update(ctx)
        return context


@dataclass
class StopConditionProcessor:
    """
    Processor for handling stop conditions with improved error handling and flexibility.
    Attributes:
        stop_condition: The condition that determines when to stop processing
        exception: Any exception that occurred during processing
        message: Optional message for logging or debugging
        logger: Optional logger instance for structured logging
    """

    stop_condition: typing.Union[StopCondition, typing.List[StopCondition]]
    exception: typing.Optional[Exception] = None
    message: typing.Optional[str] = None
    logger: typing.Optional[logging.Logger] = None

    def __post_init__(self):
        """Validate initialization parameters."""
        if not self.logger:
            self.logger = logging.getLogger(__name__)

    def should_stop(self, success: bool = True) -> bool:
        """
        Determine if processing should stop based on the current state.
        Args:
            success: Whether the operation was successful
        Returns:
            bool: True if processing should stop, False otherwise
        """
        if self.stop_condition == StopCondition.NEVER:
            return False

        if isinstance(self.stop_condition, (list, tuple)):
            return any(
                self._evaluate_single_condition(cond, success)
                for cond in self.stop_condition
            )

        return self._evaluate_single_condition(self.stop_condition, success)

    def _evaluate_single_condition(
        self, condition: StopCondition, success: bool
    ) -> bool:
        """Evaluate a single stop condition."""
        if condition == StopCondition.NEVER:
            return False
        elif condition == StopCondition.ON_SUCCESS:
            return success and self.exception is None
        elif condition == StopCondition.ON_ERROR:
            return not success or self.exception is not None
        elif condition == StopCondition.ON_ANY:
            return True
        else:
            self.logger.warning(f"Unknown stop condition: {condition}")
            return False

    def on_success(self) -> bool:
        """
        Handle successful operation completion.
        Returns:
            bool: True if processing should stop
        """
        self.exception = None
        should_stop = self.should_stop(success=True)

        if should_stop:
            self._log_stop_decision("success")

        return should_stop

    def on_error(
        self, exception: Exception, message: typing.Optional[str] = None
    ) -> bool:
        """
        Handle error during operation.
        Args:
            exception: The exception that occurred
            message: Optional additional message
        Returns:
            bool: True if processing should stop
        """
        self.exception = exception
        if message:
            self.message = message

        should_stop = self.should_stop(success=False)

        if should_stop:
            self._log_stop_decision("error")
        return should_stop

    def reset(self):
        """Reset the processor state for reuse."""
        self.exception = None
        self.message = None

    def _log_stop_decision(self, event_type: str):
        """Log the stop decision with context."""
        context = {
            "event_type": event_type,
            "stop_condition": self.stop_condition,
            "has_exception": self.exception is not None,
            "message": self.message,
        }

        if self.exception:
            self.logger.info(
                f"Stopping on {event_type} due to {self.stop_condition}", extra=context
            )
        else:
            self.logger.debug(
                f"Stopping on {event_type} due to {self.stop_condition}", extra=context
            )

    def get_status(self) -> dict:
        """Get current processor status for debugging."""
        return {
            "stop_condition": self.stop_condition,
            "has_exception": self.exception is not None,
            "exception_type": type(self.exception).__name__ if self.exception else None,
            "message": self.message,
        }


class EventBase(_RetryMixin, _ExecutorInitializerMixin, abc.ABC):
    """
    Abstract base class for event in the pipeline system.

    This class serves as a base for event-related tasks and defines common
    properties for event execution, which can be customized in subclasses.

    Class Attributes:
        executor (Type[Executor]): The executor type used to handle event execution.
                                    Defaults to DefaultExecutor.
        executor_config (ExecutorInitializerConfig): Configuration settings for the executor.
                                                    Defaults to None.
         result_evaluation_strategy(ExecutionResultEvaluationStrategyBase): The strategy to use in evaluating the
                                    results of the execution of this event in the pipeline. This will inform
                                    the pipeline as to the next execution path to take.

    Result Evaluation Strategies:
        ALL_MUST_SUCCEED/AllTasksMustSucceedStrategy: The event is considered successful only if all the tasks within the event
                                        succeeded. If any task fails, the evaluation should be marked as a failure.

        NO_FAILURES_ALLOWED/NoFailuresAllowedStrategy: The event is considered a failure if any of the tasks fail. Even if some tasks
                                    succeed, a failure in any one task results in the event being considered a failure.

        ANY_MUST_SUCCEED/AnyTaskMustSucceedStrategy: The event is considered successful if at least one of the tasks succeeded.
                                    This means that if any task succeeds, the event will be considered successful,
                                    even if others fail.

        MAJORITY_MUST_SUCCEED: Event succeeds if a majority of tasks succeed

    Subclasses must implement the `process` method to define the logic for
    processing pipeline data.
    """

    # how we want the execution results of this event to be evaluated by the pipeline
    result_evaluation_strategy: ExecutionResultEvaluationStrategyBase = (
        ResultEvaluationStrategies.ALL_MUST_SUCCEED
    )

    # Class-level registry to cache discovered subclasses
    _subclass_registry: typing.Dict[typing.Type, typing.Set[typing.Type]] = {}

    # WeakSet to automatically clean up when classes are garbage collected
    _all_event_classes: "weakref.WeakSet[typing.Type[EventBase]]" = weakref.WeakSet()

    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses when they're defined"""
        super().__init_subclass__(**kwargs)

        # Register this class in the global registry
        EventBase._all_event_classes.add(cls)

        # Clear the cache for affected parent classes
        for parent in cls.__mro__[1:]:  # Skip self
            if parent in EventBase._subclass_registry:
                del EventBase._subclass_registry[parent]

    def __init__(
        self,
        execution_context: "ExecutionContext",
        task_id: str,
        *args,
        previous_result: typing.Union[typing.List[EventResult], EMPTY] = EMPTY,
        stop_condition: StopCondition = StopCondition.NEVER,
        run_bypass_event_checks: bool = False,
        options: "Options" = None,
        **kwargs,
    ):
        """
        Initializes an EventBase instance with the provided execution context and configuration.

        This constructor is used to set up the event with the necessary context for execution,
        as well as optional configuration for handling previous results and exceptions.

        Args:
            execution_context (EventExecutionContext): The context in which the event will be executed,
                                                      providing access to execution-related data.
            task_id (str): The PipelineTask for this event.
            previous_result (Any, optional): The result of the previous event execution.
                                              Defaults to `EMPTY` if not provided.
            stop_on_exception (bool, optional): Flag to indicate whether the event should stop execution
                                                 if an exception occurs. Defaults to `False`.
            stop_on_success (bool, optional): Flag to indicate whether the event should stop execution
                                          if it is successful. Defaults to `False`.
            stop_on_error (bool, optional): Flag to indicate whether the event should stop execution
                                        if an error occurs. Defaults to `False`.
            options (Options, optional): Additional options to pass to the event constructor.
                                        This is automatically assigned at run time

        """
        super().__init__(*args, **kwargs)

        self._execution_context = execution_context
        self._task_id = task_id
        self.options = options
        self.previous_result = previous_result
        self.stop_condition = StopConditionProcessor(
            stop_condition=stop_condition, logger=logger
        )
        self.run_bypass_event_checks = run_bypass_event_checks

        self.get_retry_policy()  # config retry if error

        self._init_args = get_function_call_args(self.__class__.__init__, locals())
        self._call_args = EMPTY

        event_init.emit(sender=self.__class__, event=self, init_kwargs=self._init_args)

    def get_init_args(self):
        return self._init_args

    def get_call_args(self):
        return self._call_args

    def goto(
        self,
        descriptor: int,
        result_success: bool,
        result: typing.Any,
        reason="manual",
        execute_on_event_method: bool = True,
    ) -> None:
        """
        Transitions to the new sub-child of parent task with the given descriptor
        while optionally processing the result.
        Args:
            descriptor (int): The identifier of the next task to switch to.
            result_success (bool): Indicates if the current task succeeded or failed.
            result (typing.Any): The result data to pass to the next task.
            reason (str, optional): Reason for the task switch. Defaults to "manual".
            execute_on_event_method (bool, optional): If True, processes the result via
                success/failure handlers; otherwise, wraps it in `EventResult`.
        """
        if not isinstance(descriptor, int):
            raise ValueError("Descriptor must be an integer between 0 to 9")

        if execute_on_event_method:
            if result_success:
                res = self.on_success(result)
            else:
                res = self.on_failure(result)
        else:
            res = EventResult(
                error=not result_success,
                content=result,
                task_id=self._task_id,
                event_name=self.__class__.__name__,
                call_params=self._call_args,
                init_params=self._init_args,
            )
        raise SwitchTask(
            current_task_id=self._task_id,
            next_task_descriptor=descriptor,
            result=res,
            reason=reason,
        )

    @classmethod
    def register_event(cls, event_klass: typing.Type["EventBase"]):
        if not issubclass(event_klass, EventBase):
            raise ValueError("event_klass must be a subclass of EventBase")

        # Register this class in the global registry
        EventBase._all_event_classes.add(cls)

        # Clear the cache for affected parent classes
        for parent in cls.__mro__[1:]:  # Skip self
            if parent in EventBase._subclass_registry:
                del EventBase._subclass_registry[parent]

    @classmethod
    def evaluator(cls) -> EventEvaluator:
        """
        Get the event evaluator for the current task.
        :return: Evaluator for the current task.
        """
        if cls.result_evaluation_strategy is None:
            raise ImproperlyConfigured("No result evaluation strategy specified")
        if not isinstance(
            cls.result_evaluation_strategy, ExecutionResultEvaluationStrategyBase
        ):
            raise ImproperlyConfigured(
                f"'{cls.__name__}' is not a valid result evaluation strategy"
            )
        return EventEvaluator(cls.result_evaluation_strategy)

    def can_bypass_current_event(self) -> typing.Tuple[bool, typing.Any]:
        """
        Determines if the current event execution can be bypassed, allowing pipeline
        processing to continue to the next event regardless of validation or execution failures.

        This method evaluates custom bypass conditions defined for this specific event.
        When it returns True, the pipeline will skip the current event's execution
        and proceed to the next event in the sequence. When False, normal execution
        and error handling will occur.

        The bypass decision is typically based on business rules such as:
        - Event is optional in certain contexts
        - Alternative processing path exists
        - Specific data conditions make this event unnecessary

        Returns (Tuple):
            bool: True if the event can be bypassed, False if normal execution should occur
            data: Result data to pass to the next event.
        Example:
            In a shipping pipeline, certain validation steps might be bypassed
            for internal transfers while being required for external shipments.
        """
        return False, None

    @abc.abstractmethod
    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        """
        Processes pipeline data and executes the associated logic.

        This method must be implemented by any class inheriting from EventBase.
        It defines the logic for processing pipeline data, taking in any necessary
        arguments, and returning a tuple containing:
            - A boolean indicating the success or failure of the processing.
            - The result of the processing, which could vary based on the event logic.

        Returns:
            A tuple (success_flag, result), where:
                - success_flag (bool): True if processing is successful, False otherwise.
                - result (Any): The output or result of the processing, which can vary.
        """
        raise NotImplementedError()

    def event_result(
        self, error: bool, content: typing.Dict[str, typing.Any]
    ) -> EventResult:
        return EventResult(
            error=error,
            task_id=self._task_id,
            event_name=self.__class__.__name__,
            content=content,
            call_params=self.get_call_args(),
            init_params=self.get_init_args(),
        )

    def on_success(self, execution_result) -> EventResult:
        self.stop_condition.message = execution_result

        event_called.emit(
            sender=self.__class__,
            event=self,
            init_args=self.get_init_args(),
            call_args=self.get_call_args(),
            hook_type="on_success",
            result=execution_result,
        )

        if self.stop_condition.on_success():
            raise StopProcessingError(
                message=execution_result,
                exception=None,
                stop_condition=self.stop_condition,
                params={
                    "init_args": self._init_args,
                    "call_args": self._call_args,
                    "event_name": self.__class__.__name__,
                    "task_id": self._task_id,
                },
            )

        return self.event_result(False, execution_result)

    def on_failure(self, execution_result) -> EventResult:
        event_called.emit(
            sender=self.__class__,
            event=self,
            init_args=self.get_init_args(),
            call_args=self.get_call_args(),
            hook_type="on_failure",
            result=execution_result,
        )

        if isinstance(execution_result, Exception):
            execution_result = (
                execution_result.exception
                if execution_result.__class__ == MaxRetryError
                else execution_result
            )

        if self.stop_condition.on_error(
            exception=execution_result,
            message=f"Error occurred while processing event '{self.__class__.__name__}'",
        ):
            raise StopProcessingError(
                message=self.stop_condition.message,
                exception=execution_result,
                params={
                    "init_args": self._init_args,
                    "call_args": self._call_args,
                    "event_name": self.__class__.__name__,
                    "task_id": self._task_id,
                },
            )

        return self.event_result(True, execution_result)

    @classmethod
    @lru_cache(maxsize=128)
    def get_event_klasses(cls) -> frozenset:
        """
        Optimized version using breadth-first search with caching.
        Returns frozenset for immutability and better caching.
        """
        if cls in cls._subclass_registry:
            return frozenset(cls._subclass_registry[cls])

        # Use BFS instead of DFS to avoid deep recursion
        discovered = set()
        queue = deque([cls])
        visited = set()

        while queue:
            current_class = queue.popleft()

            if current_class in visited:
                continue
            visited.add(current_class)

            # Get direct subclasses
            for subclass in current_class.__subclasses__():
                if subclass not in discovered:
                    discovered.add(subclass)
                    queue.append(subclass)

        # Cache the result
        cls._subclass_registry[cls] = discovered
        return frozenset(discovered)

    @classmethod
    def get_all_event_classes(cls) -> typing.Set[typing.Type["EventBase"]]:
        """
        return all registered event classes.
        This is O(1) but returns ALL event classes, not just subclasses.
        """
        return set(cls._all_event_classes)

    @classmethod
    def get_direct_subclasses(cls) -> typing.Set[typing.Type["EventBase"]]:
        """Get only direct subclasses (one level down)"""
        return set(cls.__subclasses__())

    @classmethod
    def clear_class_cache(cls):
        """Clear the cached subclass registry"""
        cls._subclass_registry.clear()
        # Clear LRU cache
        cls.get_event_klasses.cache_clear()

    def __call__(self, *args, **kwargs):
        self._call_args = get_function_call_args(self.__class__.__call__, locals())

        if self.run_bypass_event_checks:
            try:
                should_skip, data = self.can_bypass_current_event()
            except Exception as e:
                logger.error(
                    "Error in event setup status checks: %s", str(e), exc_info=e
                )
                raise

            if should_skip:
                execution_result = {
                    "status": 1,
                    "skip_event_execution": should_skip,
                    "data": data,
                }
                return self.on_success(execution_result)

        try:
            self._execution_status, execution_result = self.retry(
                self.process, *args, **kwargs
            )
        except MaxRetryError as e:
            logger.error(str(e), exc_info=e.exception)
            return self.on_failure(e)
        except Exception as e:
            logger.error(str(e), exc_info=e)
            return self.on_failure(e)
        if self._execution_status:
            return self.on_success(execution_result)
        return self.on_failure(execution_result)
