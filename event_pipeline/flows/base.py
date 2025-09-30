import typing
import logging
from abc import ABC, abstractmethod
from concurrent.futures._base import Executor
from pydantic_mini import BaseModel, MiniAnnotated, Attrib
from event_pipeline.constants import EMPTY
from event_pipeline.import_utils import import_string
from event_pipeline.mixins import ObjectIdentityMixin
from event_pipeline.parser.operator import PipeType
from event_pipeline.runners.execution_data import ExecutionContext
from event_pipeline.utils import build_event_arguments_from_pipeline
from event_pipeline.parser.protocols import TaskGroupingProtocol, TaskProtocol

if typing.TYPE_CHECKING:
    from event_pipeline import Event


logger = logging.getLogger(__name__)


def format_task_profiles(
    task_profiles: typing.Any,
) -> typing.Set[typing.Union[TaskProtocol, TaskGroupingProtocol]]:
    if isinstance(task_profiles, (TaskProtocol, TaskGroupingProtocol)):
        return {task_profiles}
    return task_profiles


class FlowBase(ObjectIdentityMixin, BaseModel, ABC):
    # The execution context for this flow
    context: ExecutionContext

    #  The profile of the tasks to be executed
    task_profiles: MiniAnnotated[
        typing.Set[typing.Union["TaskProtocol", "TaskGroupingProtocol"]],
        Attrib(default_factory=set, pre_formatter=format_task_profiles, min_length=1),
    ]

    class Config:
        disable_type_check = False
        disable_all_validations = False

    def __model_init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def add_task_profile(
        self, task_profile: typing.Union["TaskProtocol", "TaskGroupingProtocol"]
    ) -> None:
        """
        Add a task profile to this flow.
        Args:
            task_profile: The task profile to add.
        """
        self.task_profiles.add(task_profile)

    def configure_event(self, event: "Event", task_profile: "TaskProtocol") -> None:
        """
        Configure event for this flow.
        Args:
            event: The event to configure.
            task_profile: The task profile that this event is configured for.
        """
        options_retries = (
            task_profile.options and task_profile.options.retry_attempts or 0
        )
        total_retries = options_retries
        if total_retries > 1:
            event_retry_policy = event.get_retry_policy()
            if event_retry_policy:
                event_retry_policy.max_attempts = total_retries
            else:
                event.config_retry_policy(max_attempts=total_retries)

    def get_initialized_event(
        self, task_profile: "TaskProtocol"
    ) -> typing.Tuple["Event", typing.Dict[str, typing.Any]]:
        """
        Initialized and configure event
        :param task_profile: The task profile to initialize
        :return: A tuple of the initialized event and the event call arguments
        """
        event_klass = task_profile.get_event_class()

        logger.info(f"Initializing '{task_profile.event}'")

        event_init_args, event_call_ars = build_event_arguments_from_pipeline(
            event_klass, self.context.pipeline
        )

        event_init_args = event_init_args or {}
        event_call_args = event_call_ars or {}

        event_init_args["execution_context"] = self.context
        event_init_args["task_id"] = task_profile.get_id()

        # Let's pass the options given in the pointy script to the event
        if task_profile.options:
            event_init_args["options"] = task_profile.options

        if task_profile.is_parallel_execution_node:
            parent = task_profile.get_parent_node_for_parallel_execution()
            pointer_type = parent.get_task_pointer_type()
        else:
            pointer_type = task_profile.get_task_pointer_type()

        if pointer_type == PipeType.PIPE_POINTER:
            if self.previous_context:
                event_init_args["previous_result"] = (
                    self.previous_context.execution_result
                )
            else:
                event_init_args["previous_result"] = EMPTY

        event = event_klass(**event_init_args)

        # configure the event
        self.configure_event(event, task_profile)

        return event, event_call_args

    @staticmethod
    async def get_task_executor_from_options(
        task_profile: typing.Union[TaskProtocol, TaskGroupingProtocol],
    ) -> typing.Optional[typing.Type["Executor"]]:
        """
        Get the executor class from the task profile options if available.
        Args:
            task_profile: The task profile to get the executor class from.
        Returns:
            The executor class or None if not found or invalid.
        """
        if task_profile.options:
            executor_str = task_profile.options.executor
            if executor_str is not None:
                try:
                    instance = import_string(executor_str)
                    if not issubclass(instance, Executor):
                        raise ValueError(f"Unsupported executor type {executor_str}")
                    return instance
                except ImportError:
                    logger.warning("Could not import executor '%s'", executor_str)
                except ValueError as e:
                    logger.warning(str(e))
        return None

    @abstractmethod
    async def get_flow_executor(self, *args, **kwargs) -> typing.Type[Executor]:
        raise NotImplementedError()

    def get_flow_executor_config(
        self, task_profile, **config
    ) -> typing.Dict[str, typing.Any]:
        pass

    @abstractmethod
    async def run(self) -> None:
        raise NotImplementedError()

    @classmethod
    def setup_next_flow(
        cls, next_flow: "FlowBase", previous: typing.Optional["FlowBase"] = None
    ) -> None:
        pass
