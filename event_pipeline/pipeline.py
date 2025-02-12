import os
import re
import inspect
import typing
import copy
from collections import OrderedDict, ChainMap, deque
from functools import lru_cache
from inspect import Signature, Parameter

try:
    import graphviz
except ImportError:
    graphviz = None

from .task import PipelineTask, EventExecutionContext, PipeType
from .constants import PIPELINE_FIELDS, PIPELINE_STATE, UNKNOWN, EMPTY
from .utils import generate_unique_id, GraphTree
from .exceptions import (
    ImproperlyConfigured,
    BadPipelineError,
    EventDone,
    EventDoesNotExist,
)


class TreeExtraData:
    def __init__(self, pipe_type: PipeType):
        self.pipe_type = pipe_type


class CacheFieldDescriptor(object):
    """
    TODO: Add backend for persisting cache in a redis/memcache store
    """

    def __set_name__(self, owner, name):
        self.name = name

    def __set__(self, instance, value):
        if instance is None:
            return self
        if instance.__dict__.get(self.name) is None:
            instance.__dict__[self.name] = OrderedDict()

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        dt = instance.__dict__.get(self.name)
        if dt is None:
            dt = OrderedDict()
            setattr(instance, self.name, dt)
        return instance.__dict__[self.name]


class PipelineState(object):
    pipeline_cache = CacheFieldDescriptor()

    def __init__(self, pipeline: PipelineTask):
        self.start: PipelineTask = pipeline

    def clear(self, instance: typing.Union["Pipeline", str]):
        instance_key = self.get_cache_key(instance)
        cache_fields = self.check_cache_exists(instance)
        if cache_fields:
            for field in cache_fields:
                try:
                    self.__dict__[field].pop(instance_key)
                except (AttributeError, KeyError):
                    pass

    @staticmethod
    def get_cache_key(instance: typing.Union["Pipeline", str]):
        return instance.get_cache_key() if not isinstance(instance, str) else instance

    def check_cache_exists(self, instance: typing.Union["Pipeline", str]):
        keys = set()
        instance_key = self.get_cache_key(instance)
        for field, value in self.__dict__.items():
            if isinstance(value, (dict, OrderedDict)) and instance_key in value:
                keys.add(field)
        return keys

    def cache(self, instance: typing.Union["Pipeline", str]):
        cache_fields = self.check_cache_exists(instance)
        instance_key = self.get_cache_key(instance)
        return ChainMap(*(self.__dict__[field][instance_key] for field in cache_fields))

    def set_cache(self, instance, instance_cache_field, *, field_name=None, value=None):
        if value is None:
            return
        instance_key = self.get_cache_key(instance)
        cache = self.__dict__.get(instance_cache_field)
        if cache and instance_key in cache:
            collection = cache[instance_key]
            if instance_key not in collection:
                self.__dict__[instance_cache_field][instance_key] = OrderedDict()
        else:
            self.__dict__[instance_cache_field] = OrderedDict(
                [(instance_key, OrderedDict())]
            )

        self.__dict__[instance_cache_field][instance_key][field_name] = value

    def set_cache_for_pipeline_field(self, instance, field_name, value):
        self.set_cache(
            instance=instance,
            instance_cache_field="pipeline_cache",
            field_name=field_name,
            value=value,
        )


class PipelineMeta(type):

    def __new__(cls, name, bases, namespace, **kwargs):
        parents = [b for b in bases if isinstance(b, PipelineMeta)]
        if not parents:
            return super().__new__(cls, name, bases, namespace)

        from .fields import InputDataField

        pointy_path = pointy_str = None

        input_data_fields = OrderedDict()

        for f_name, field in namespace.items():
            if isinstance(field, InputDataField):
                input_data_fields[f_name] = field

        new_class = super().__new__(cls, name, bases, namespace, **kwargs)
        meta_class = getattr(new_class, "Meta", getattr(new_class, "meta", None))
        if meta_class:
            if inspect.isclass(new_class):
                pointy_path = getattr(meta_class, "file", None)
                pointy_str = getattr(meta_class, "pointy", None)
            elif isinstance(meta_class, dict):
                pointy_path = meta_class.pop("file", None)
                pointy_str = meta_class.pop("pointy", None)
        else:
            pointy_path = "."

        if not pointy_str:
            pointy_file = cls.find_pointy_file(
                pointy_path, class_name=f"{new_class.__name__}"
            )
            if pointy_file is None:
                raise ImproperlyConfigured(
                    f"Meta not configured for Pipeline '{new_class.__name__}'"
                )
            with open(pointy_file, "r") as f:
                pointy_str = f.read()

        try:
            pipeline = PipelineTask.build_pipeline_from_execution_code(pointy_str)
        except Exception as e:
            if isinstance(e, SyntaxError):
                raise
            raise BadPipelineError(
                f"Pipeline is improperly written. Kindly check and fix it: Reason: {str(e)}",
                exception=e,
            )

        setattr(new_class, PIPELINE_FIELDS, input_data_fields)
        setattr(new_class, PIPELINE_STATE, PipelineState(pipeline))

        return new_class

    @classmethod
    @lru_cache
    def find_pointy_file(cls, pipeline_path: str, class_name: str) -> str:
        if os.path.isfile(pipeline_path):
            return pipeline_path
        elif os.path.isdir(pipeline_path):
            return cls.directory_walk(pipeline_path, f"{class_name}.pty")

    @classmethod
    def directory_walk(cls, dir_path: str, file_name: str):
        for root, dirs, files in os.walk(dir_path):
            for name in files:
                if re.match(file_name, name, flags=re.IGNORECASE):
                    return os.path.join(root, name)
            for vdir in dirs:
                cls.directory_walk(os.path.join(root, vdir), file_name)


class Pipeline(metaclass=PipelineMeta):

    def __init__(self, *args, **kwargs):
        generate_unique_id(self)

        parameters = []
        for name, instance in self.get_fields():
            if name:
                param_args = {
                    "name": name,
                    "annotation": (
                        instance.data_type
                        if instance.data_type is not UNKNOWN
                        else typing.Any
                    ),
                    "kind": Parameter.POSITIONAL_OR_KEYWORD,
                }
                if instance.default is not EMPTY:
                    param_args["default"] = instance.default

                param = Parameter(**param_args)
                parameters.append(param)

        if parameters:
            sig = Signature(parameters)
            bounded_args = sig.bind(*args, **kwargs)
            for name, value in bounded_args.arguments.items():
                setattr(self, name, value)

        self.execution_context: typing.Optional[EventExecutionContext] = None

        super().__init__()

    @property
    def id(self):
        return generate_unique_id(self)

    def __eq__(self, other):
        if not isinstance(other, Pipeline):
            return False
        return self.id == other.id

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getstate__(self):
        instance_key = self.get_cache_key()
        state = self.__dict__.copy()
        klass_state = self.__class__.__dict__.copy()
        state["_state"] = copy.copy(klass_state["_state"])
        state["_state"].pipeline_cache = {
            instance_key: state["_state"].pipeline_cache.get(instance_key, {}).copy()
        }
        return state

    def __hash__(self):
        return hash(self.id)

    def start(self, force_rerun: bool = False):
        if self.execution_context and not force_rerun:
            raise EventDone("Done executing pipeline")
        self.execution_context = None
        sink_queue = deque()
        PipelineTask.execute_task(
            self._state.start,
            previous_context=self.execution_context,
            pipeline=self,
            sink_queue=sink_queue,
        )

    def get_cache_key(self):
        return f"pipeline_{self.__class__.__name__}_{self.id}"

    @classmethod
    def get_fields(cls):
        for name, klass in getattr(cls, PIPELINE_FIELDS, {}).items():
            yield name, klass

    def get_pipeline_tree(self) -> GraphTree:
        state: PipelineTask = self._state.start
        if state:
            tree = GraphTree()
            for node in state.bf_traversal(state):
                tag = ""
                if node.is_conditional:
                    tag = " (?)"

                if node.is_descriptor_task:
                    tag = " (No)" if node._descriptor == 0 else " (Yes)"

                if node.is_sink:
                    tag = " (Sink)"

                tree.create_node(
                    tag=f"{node.event}{tag}",
                    identifier=node.id,
                    parent=node.parent_node.id if node.parent_node else None,
                    data=TreeExtraData(pipe_type=node.get_pointer_type_to_this_event()),
                )
            return tree

    def draw_ascii_graph(self):
        tree = self.get_pipeline_tree()
        if tree:
            tree.show(line_type="ascii-emv")

    def draw_graphviz_image(self, directory="pipeline-graphs"):
        if graphviz is None:
            return
        tree = self.get_pipeline_tree()
        if tree:
            data = tree.return_graphviz_data()
            src = graphviz.Source(data, directory=directory)
            src.render(format="png", outfile=f"{self.__class__.__name__}.png")

    @classmethod
    def load_class_by_id(cls, pk: str):
        cache_keys = cls._state.check_cache_exists(pk)
        if not cache_keys:
            return cls()
        cache = cls._state.cache(pk)

        # restore fields
        kwargs = {}
        for key, value in cache.get("pipeline_cache", {}).items():
            kwargs[key] = value

        instance = cls(**kwargs)
        setattr(instance, "_id", pk)

        # then restore states as well
        # i.e. current and next from pipeline_cache

        return instance

    def get_task_by_id(self, pk: str):
        """
        Retrieves a task from the pipeline by its unique identifier.

        This method searches for a task in the pipeline using the provided unique identifier.
        If the task is not found, it raises an `EventDoesNotExist` exception to signal that the requested
        task does not exist in the queue.

        Args:
            pk (str): The unique identifier (primary key) of the task to retrieve.

        Returns:
            Task: The task object associated with the given primary key if found.

        Raises:
            EventDoesNotExist: If no task with the given primary key exists in the pipeline.
        """
        state: PipelineTask = self._state.start
        if state:
            for task in state.bf_traversal(state):
                if task.id == pk:
                    return task
        raise EventDoesNotExist(f"Task '{pk}' does not exists", code=pk)
