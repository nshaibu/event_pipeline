import typing
from collections import deque

from event_pipeline.mixins import ObjectIdentityMixin
from event_pipeline.parser.options import Options
from event_pipeline.parser.operator import PipeType
from event_pipeline.parser.conditional import ConditionalNode

if typing.TYPE_CHECKING:
    from event_pipeline.parser.protocols import TaskProtocol, TaskGroupingProtocol


class TaskBase(ObjectIdentityMixin):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # options specified in pointy scripts for tasks are kept here
        self.options: typing.Optional[Options] = None

        # attributes for when a task is created from a descriptor
        self._descriptor: typing.Optional[int] = None
        self._descriptor_pipe: typing.Optional[PipeType] = None

        self.parent_node: typing.Optional[
            typing.Union["TaskProtocol", "TaskGroupingProtocol"]
        ] = None

        # sink event this is where the conditional events collapse
        # into after they are done executing
        self.sink_node: typing.Optional[
            typing.Union["TaskProtocol", "TaskGroupingProtocol"]
        ] = None
        self.sink_pipe: typing.Optional[PipeType] = None

        self.condition_node: ConditionalNode = ConditionalNode()

    def __getstate__(self):
        state = self.__dict__.copy()
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def get_id(self) -> str:
        return self.id

    @property
    def descriptor(self) -> typing.Optional[int]:
        return self._descriptor

    @descriptor.setter
    def descriptor(self, value: typing.Optional[int]) -> None:
        if value is None:
            raise ValueError("Descriptor cannot be None")
        if not isinstance(value, int):
            raise TypeError("Descriptor must be an integer")
        if 0 > value or value > 9:
            raise ValueError("Descriptor must be between 0 and 9")
        self._descriptor = value

    @property
    def descriptor_pipe(self) -> typing.Optional["PipeType"]:
        return self._descriptor_pipe

    @descriptor_pipe.setter
    def descriptor_pipe(self, value: "PipeType") -> None:
        self._descriptor_pipe = value

    @property
    def is_conditional(self):
        return len(self.condition_node.get_descriptors()) > 1

    @property
    def is_descriptor_task(self):
        """
        Determines if the current task is a descriptor node.

        A descriptor node is a conditional node that is executed based on the result
        of its parent node's execution. In the pointy language, a value of 0 represents
        a failure descriptor, and a value of 1 represents a success descriptor.

        Returns:
            bool: True if the task is a descriptor node, False otherwise.
        """
        return self._descriptor is not None or self._descriptor_pipe is not None

    @property
    def is_sink(self) -> bool:
        """
        Determines if the current PipelineTask is a sink node.

        A sink node is executed after all the child nodes of its parent have
        finished executing. This method checks if the current task is classified
        as a sink node in the pipeline.

        Returns:
            bool: True if the task is a sink node, False otherwise.
        """
        parent = self.parent_node
        if parent and not self.is_descriptor_task:
            return parent.sink_node == self
        return False

    @property
    def is_parallel_execution_node(self):
        """
        Determines whether the current node is configured for parallel execution.

        This method evaluates whether the current node is configured for parallel execution by
        checking two conditions:
        1. It verifies if the `on_success_pipe` of the current node is set to `PipeType.PARALLELISM`.
        2. It retrieves the pointer type to this event and checks if it is also `PipeType.PARALLELISM`.

        If either of these conditions is true, the method returns True, indicating that parallel execution
        is applicable; otherwise, it returns False.
        """

        pointer_to_node = self.get_pointer_to_task()
        return (
            self.condition_node.on_success_pipe == PipeType.PARALLELISM
            or pointer_to_node == PipeType.PARALLELISM
        )

    def get_pointer_to_task(self) -> typing.Optional["PipeType"]:
        pipe_type = None
        if self.parent_node is not None:
            if (
                self.parent_node.condition_node.on_success_event
                and self.parent_node.condition_node.on_success_event == self
            ):
                pipe_type = self.parent_node.condition_node.on_success_pipe
            elif (
                self.parent_node.condition_node.on_failure_event
                and self.parent_node.condition_node.on_failure_event == self
            ):
                pipe_type = self.parent_node.condition_node.on_failure_pipe
            elif self.parent_node.sink_node and self.parent_node.sink_node == self:
                pipe_type = self.parent_node.sink_pipe
            else:
                descriptor = self._descriptor
                if descriptor is None:
                    descriptor = -1  # sentinel for no descriptor

                # Handle custom descriptors
                descriptor_profile = (
                    self.parent_node.condition_node.get_descriptor_config(descriptor)
                )
                if descriptor_profile is None:
                    return None
                if descriptor_profile:
                    pipe_type = descriptor_profile.pipe
                else:
                    pipe_type = self.descriptor_pipe

        return pipe_type

    def get_children(self):
        children = []
        if self.sink_node:
            children.append(self.sink_node)
        for node_config in self.condition_node.get_descriptors():
            children.append(node_config.task)
        return children

    def get_root(self) -> typing.Union["TaskProtocol", "TaskGroupingProtocol"]:
        if self.parent_node is None:
            node = self
            if typing.TYPE_CHECKING:
                node = typing.cast(
                    typing.Union["TaskProtocol", "TaskGroupingProtocol"], node
                )
            return node
        return self.parent_node.get_root()

    def get_dot_node_data(self) -> str:
        raise NotImplementedError

    def get_task_count(self) -> int:
        root = self.get_root()
        nodes = list(self.bf_traversal(root))
        return len(nodes)

    def get_descriptor(self, descriptor: int) -> typing.Optional["TaskProtocol"]:
        target = self.condition_node.get_descriptor_config(descriptor)
        if target:
            return target.task
        return None

    @classmethod
    def bf_traversal(
        cls, node: typing.Optional[typing.Union["TaskProtocol", "TaskGroupingProtocol"]]
    ):
        """
        Performs a breadth-first traversal of the task tree starting from the given node.

        Despite the method name, this traversal is depth-first, not breadth-first.
        Yields each node in the tree.
        """
        if node:
            yield node

            for child in node.get_children():
                yield from cls.bf_traversal(child)

    def get_parallel_nodes(
        self,
    ) -> typing.Deque[typing.Union["TaskProtocol", "TaskGroupingProtocol"]]:
        parallel_tasks = deque()
        task = self
        while task and task.condition_node.on_success_pipe == PipeType.PARALLELISM:
            parallel_tasks.append(task)
            task = task.condition_node.on_success_event

        parallel_tasks.append(task)
        return parallel_tasks
