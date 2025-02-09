import abc
import typing
import logging
import multiprocessing as mp
from concurrent.futures import Executor, ProcessPoolExecutor
from .constants import EMPTY, EventResult
from .executors.default_executor import DefaultExecutor
from .utils import get_function_call_args
from .exceptions import StopProcessingError


logger = logging.getLogger(__name__)


class EventBase(abc.ABC):
    """
    Abstract base class for event in the pipeline system.

    This class serves as a base for event-related tasks and defines common
    properties for event execution, which can be customized in subclasses.

    Attributes:
        executor (Type[Executor]): The executor type used to handle event execution.
                                    Defaults to DefaultExecutor.
        max_workers (Union[int, EMPTY]): The maximum number of workers allowed
                                          for event processing. Defaults to EMPTY.
        max_tasks_per_child (Union[int, EMPTY]): The maximum number of tasks
                                                  that can be assigned to each worker.
                                                  Defaults to EMPTY.
        thread_name_prefix (Union[str, EMPTY]): The prefix to use for naming threads
                                                 in the event execution. Defaults to EMPTY.

    Subclasses must implement the `process` method to define the logic for
    processing pipeline data.
    """

    executor: typing.Type[Executor] = DefaultExecutor

    max_workers: typing.Union[int, EMPTY] = EMPTY
    max_tasks_per_child: typing.Union[int, EMPTY] = EMPTY
    thread_name_prefix: typing.Union[str, EMPTY] = EMPTY

    def __init__(
        self,
        execution_context: "EventExecutionContext",
        task_id: str,
        previous_result=EMPTY,
        stop_on_exception: bool = False,
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
        self._execution_context = execution_context
        self._task_id = task_id
        self.previous_result = previous_result
        self.stop_on_exception = stop_on_exception

        self._init_args = get_function_call_args(self.__class__.__init__, locals())
        self._call_args = EMPTY

    def get_init_args(self):
        return self._init_args

    def get_call_args(self):
        return self._call_args

    @classmethod
    def get_executor_class(cls) -> typing.Type[Executor]:
        return cls.executor

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
            is_error=False,
            detail=execution_result,
            task_id=self._task_id,
            event_name=self.__class__.__name__,
            call_params=self._call_args,
            init_params=self._init_args,
        )

    def on_failure(self, execution_result) -> EventResult:
        if isinstance(execution_result, Exception):
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
            is_error=True,
            detail=execution_result,
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
        params = get_function_call_args(executor.__init__, self.__class__)
        context.update(params)
        return context

    def __call__(self, *args, **kwargs):
        self._call_args = get_function_call_args(self.__class__.__call__, locals())
        try:
            self._execution_status, execution_result = self.process(*args, **kwargs)
        except Exception as e:
            logger.exception(str(e), exc_info=e)
            return self.on_failure(e)
        if self._execution_status:
            return self.on_success(execution_result)
        return self.on_failure(execution_result)
