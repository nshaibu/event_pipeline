import abc
import typing
import logging
import time
import multiprocessing as mp
from enum import Enum
from dataclasses import dataclass, field
from concurrent.futures import Executor, ProcessPoolExecutor
from .result import EventResult, ResultSet
from .constants import EMPTY, MAX_EVENTS_RETRIES, MAX_BACKOFF
from .executors.default_executor import DefaultExecutor
from .utils import get_function_call_args
from .exceptions import StopProcessingError, MaxRetryError
from .signal.signals import (
    event_execution_retry,
    event_execution_retry_done,
    event_init,
)


__all__ = [
    "EventBase",
    "RetryPolicy",
    "EvaluationContext",
    "ExecutorInitializerConfig",
    "EventExecutionEvaluationState",
]


logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from .task import EventExecutionContext


@dataclass
class ExecutorInitializerConfig(object):
    """
    Configuration class for executor initialization.

        max_workers (Union[int, EMPTY]): The maximum number of workers allowed
                                          for event processing. Defaults to EMPTY.
        max_tasks_per_child (Union[int, EMPTY]): The maximum number of tasks
                                                  that can be assigned to each worker.
                                                  Defaults to EMPTY.
        thread_name_prefix (Union[str, EMPTY]): The prefix to use for naming threads
                                                 in the event execution. Defaults to EMPTY.
    """

    max_workers: typing.Union[int, EMPTY] = EMPTY
    max_tasks_per_child: typing.Union[int, EMPTY] = EMPTY
    thread_name_prefix: typing.Union[str, EMPTY] = EMPTY


@dataclass
class RetryPolicy(object):
    max_attempts: int = field(init=True, default=MAX_EVENTS_RETRIES)
    backoff_factor: float = field(init=True, default=0.05)
    max_backoff: float = field(init=True, default=MAX_BACKOFF)
    retry_on_exceptions: typing.List[typing.Type[Exception]] = field(
        default_factory=list
    )


class _RetryMixin(object):

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
        return (
            self.retry_policy
            and self.retry_policy.retry_on_exceptions
            and isinstance(exception, Exception)
            and any(
                [
                    isinstance(exception, exc)
                    and exception.__class__.__name__ == exc.__name__
                    for exc in self.retry_policy.retry_on_exceptions
                    if exc
                ]
            )
        )

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


class _ExecutorInitializerMixin(object):

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
                self.executor_config = ExecutorInitializerConfig(**self.executor_config)
        else:
            self.executor_config = ExecutorInitializerConfig()
        return self.executor_config

    def is_multiprocessing_executor(self):
        return self.get_executor_class() == ProcessPoolExecutor

    def get_executor_context(self) -> typing.Dict[str, typing.Any]:
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
        return context


class EvaluationContext(Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class EventExecutionEvaluationState(Enum):
    # The event is considered successful only if all the tasks within the event succeeded.If any task fails,
    # the evaluation should be marked as a failure. This state ensures that the event is only successful
    # if every task in the execution succeeds. If even one task fails, the overall evaluation will be a failure.
    SUCCESS_ON_ALL_EVENTS_SUCCESS = "Success (All Tasks Succeeded)"

    # The event is considered a failure if any of the tasks fail. Even if some tasks
    # succeed, a failure in any one task results in the event being considered a failure.  In this state,
    # as soon as one task fails, the event is considered a failure, regardless of how many tasks succeed
    FAILURE_FOR_PARTIAL_ERROR = "Failure (Any Task Failed)"

    # This state treats the event as successful if any task succeeds. Even if other tasks fail, as long as one succeeds,
    # the event will be considered successful. This can be used in cases where partial success is enough to consider
    # the event as successful.
    SUCCESS_FOR_PARTIAL_SUCCESS = "Success (At least one Task Succeeded)"

    # This state ensures the event is only considered a failure if every task fails. If any task succeeds, the event
    # is marked as successful. This can be helpful in scenarios where the overall success is determined by the
    # presence of at least one successful task.
    FAILURE_FOR_ALL_EVENTS_FAILURE = "Failure (All Tasks Failed)"

    def _evaluate(self, result: ResultSet, errors: typing.List[Exception]) -> bool:
        has_success = len(result) > 0
        has_error = len(errors) > 0

        if self == self.SUCCESS_ON_ALL_EVENTS_SUCCESS:
            return not has_error and has_success
        elif self == self.SUCCESS_FOR_PARTIAL_SUCCESS:
            return has_success
        elif self == self.FAILURE_FOR_PARTIAL_ERROR:
            return has_error
        else:
            return not has_success and has_error

    def context_evaluation(
        self,
        result: ResultSet,
        errors: typing.List[Exception],
        context: EvaluationContext = EvaluationContext.SUCCESS,
    ) -> bool:
        """
        Evaluates the event's outcome based on both the task results and the provided context.

        This method combines the evaluation of the event (via the `evaluate` method) with
        an additional context (success or failure) to return the final outcome. Depending on
        the context, the method applies different rules to determine whether the event should
        be considered a success or failure.

        Parameters:
            result (ResultSet): A list of successful event results.
            errors (typing.List[Exception]): A list of errors or exceptions encountered during event execution.
            context (EvaluationContext, optional): The context under which the evaluation should be made.
                                                   Defaults to `EvaluationContext.SUCCESS`.

        Returns:
            bool: The final evaluation result of the event. Returns `True` if the event meets
                  the success or failure criteria defined by the current state and context.
                  Returns `False` otherwise.

        Logic:
            - If the context is `EvaluationContext.SUCCESS`:
                - If the state is either `SUCCESS_ON_ALL_EVENTS_SUCCESS` or `SUCCESS_FOR_PARTIAL_SUCCESS`,
                  the event is successful if the `evaluate` method returns `True`.
                - Otherwise, the event is considered a failure if `evaluate` returns `False`.
            - If the context is not `EvaluationContext.SUCCESS` (i.e., failure-related contexts):
                - If the state is either `FAILURE_FOR_ALL_EVENTS_FAILURE` or `FAILURE_FOR_PARTIAL_ERROR`,
                  the event is successful if the `evaluate` method returns `True`.
                - Otherwise, the event is considered a failure if `evaluate` returns `False`.
        """

        status = self._evaluate(result, errors)

        if context == EvaluationContext.SUCCESS:
            if self in [
                self.SUCCESS_ON_ALL_EVENTS_SUCCESS,
                self.SUCCESS_FOR_PARTIAL_SUCCESS,
            ]:
                return status
            return not status

        if self in [
            self.FAILURE_FOR_ALL_EVENTS_FAILURE,
            self.FAILURE_FOR_PARTIAL_ERROR,
        ]:
            return status
        return not status


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
        execution_evaluation_state: (EventExecutionEvaluationState): Focuses purely on the result of the evaluation
                                    process—whether the event was successful or failed, depending on the tasks.

    Result Evaluation States:
        SUCCESS_ON_ALL_EVENTS_SUCCESS: The event is considered successful only if all the tasks within the event
                                        succeeded. If any task fails, the evaluation should be marked as a failure.

        FAILURE_FOR_PARTIAL_ERROR: The event is considered a failure if any of the tasks fail. Even if some tasks
                                    succeed, a failure in any one task results in the event being considered a failure.

        SUCCESS_FOR_PARTIAL_SUCCESS: The event is considered successful if at least one of the tasks succeeded.
                                    This means that if any task succeeds, the event will be considered successful,
                                    even if others fail.

        FAILURE_FOR_ALL_EVENTS_FAILURE: The event is considered a failure only if all the tasks fail. If any task
                                        succeeds, the event is considered a success.

    Subclasses must implement the `process` method to define the logic for
    processing pipeline data.
    """

    execution_evaluation_state: EventExecutionEvaluationState = (
        EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS
    )

    def __init__(
        self,
        execution_context: "EventExecutionContext",
        task_id: str,
        *args,
        previous_result: typing.Union[typing.List[EventResult], EMPTY] = EMPTY,
        stop_on_exception: bool = False,
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

        """
        super().__init__(*args, **kwargs)

        self._execution_context = execution_context
        self._task_id = task_id
        self.previous_result = previous_result
        self.stop_on_exception = stop_on_exception

        self.get_retry_policy()  # config retry if error

        self._init_args = get_function_call_args(self.__class__.__init__, locals())
        self._call_args = EMPTY

        event_init.emit(sender=self.__class__, event=self, init_kwargs=self._init_args)

    def get_init_args(self):
        return self._init_args

    def get_call_args(self):
        return self._call_args

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

    def on_success(self, execution_result) -> EventResult:
        return EventResult(
            error=False,
            content=execution_result,
            task_id=self._task_id,
            event_name=self.__class__.__name__,
            call_params=self._call_args,
            init_params=self._init_args,
        )

    def on_failure(self, execution_result) -> EventResult:
        if isinstance(execution_result, Exception):
            execution_result = (
                execution_result.exception
                if execution_result.__class__ == MaxRetryError
                else execution_result
            )

            if self.stop_on_exception:
                raise StopProcessingError(
                    message=f"Error occurred while processing event '{self.__class__.__name__}'",
                    exception=execution_result,
                    params={
                        "init_args": self._init_args,
                        "call_args": self._call_args,
                        "event_name": self.__class__.__name__,
                        "task_id": self._task_id,
                    },
                )

        return EventResult(
            error=True,
            content=execution_result,
            task_id=self._task_id,
            event_name=self.__class__.__name__,
            init_params=self._init_args,
            call_params=self._call_args,
        )

    @classmethod
    def get_event_klasses(cls):
        for subclass in cls.__subclasses__():
            yield from subclass.get_event_klasses()
            yield subclass

    def __call__(self, *args, **kwargs):
        self._call_args = get_function_call_args(self.__class__.__call__, locals())
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
