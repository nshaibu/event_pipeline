import os
import re
import inspect
import typing
from collections import OrderedDict, ChainMap
from functools import lru_cache
from inspect import Signature, Parameter

try:
    import graphviz
except ImportError:
    graphviz = None

from .task import PipelineTask
from .constants import PIPELINE_FIELDS, PIPELINE_STATE, UNKNOWN, EMPTY
from .utils import generate_unique_id, GraphTree
from .exceptions import ImproperlyConfigured, BadPipelineError


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


class PipelineStateDescriptor(object):

    def __set_name__(self, owner, name):
        self.name = name

    def __set__(self, instance, value):
        if not isinstance(value, PipelineTask):
            raise TypeError
        instance.__dict__[self.name] = value

    def __get__(self, instance, owner):
        return instance.__dict__[self.name]


class PipelineState(object):
    pipeline_cache = CacheFieldDescriptor()
    result_cache = CacheFieldDescriptor()

    start = PipelineStateDescriptor()
    # current = PipelineStateDescriptor()
    # next = PipelineStateDescriptor()

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

    def set_cache_for_result_field(self, instance, field_name, value):
        self.set_cache(
            instance=instance,
            instance_cache_field="result_cache",
            field_name=field_name,
            value=value,
        )

    # def set_next_pipeline(self, instance, value):
    #     cache_key = self.get_cache_key(instance)
    #     self.__dict__[cache_key]["next"] = value
    #
    # def set_current_pipeline(self, instance, value):
    #     cache_key = self.get_cache_key(instance)
    #     self.__dict__[cache_key]["current"] = value


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
                    "kind": (
                        Parameter.POSITIONAL_ONLY
                        if instance.required
                        else Parameter.POSITIONAL_OR_KEYWORD
                    ),
                }
                if instance.default is not EMPTY:
                    kwargs["default"] = instance.default

                param = Parameter(**param_args)
                parameters.append(param)

        if parameters:
            sig = Signature(parameters)
            bounded_args = sig.bind(*args, **kwargs)
            for name, value in bounded_args.arguments.items():
                setattr(self, name, value)

    @property
    def id(self):
        return generate_unique_id(self)

    def __eq__(self, other):
        if not isinstance(other, Pipeline):
            return False
        return self.id == other.id

    def __reduce__(self):
        pass

    def __setstate__(self, state):
        state = self.__dict__.copy()
        pass

    def __getstate__(self):
        pass

    def __hash__(self):
        return hash(self.id)

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
                # else:
                #     tag = ""

                tree.create_node(
                    tag=f"{node.event}{tag}",
                    identifier=node.id,
                    parent=node.parent_node.id if node.parent_node else None,
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
            raise
        cache = cls._state.cache(pk)

        # restore fields
        kwargs = {}
        for key, value in cache.get("pipeline_cache", {}).items():
            kwargs[key] = value

        instance = cls(**kwargs)
        setattr(instance, "_id", pk)

        # then restore states as well

        return instance

    # def start_task(self, execution_str: str) -> typing.Coroutine:
    #     self._task = GS1EventBase.pipeline()
    #     self.trigger_next_event()
    #     return self._task
    #
    # def is_configured(self):
    #     return self._start_pipeline or self._next_event
    #
    # def move_to_next(self) -> typing.Optional[PipelineEvent]:
    #     if self._next_event:
    #         if self._current_pipeline is None:
    #             self._current_pipeline = self._start_pipeline
    #             return self._start_pipeline
    #
    #         self._next_event = self._current_pipeline.next_event
    #         self._current_pipeline = self._next_event
    #         return self._next_event
    #
    # def peek_next_for_event(self) -> typing.Optional["GS1EventBase"]:
    #     if self._task is None:
    #         return self._start_pipeline.event
    #
    #     if self._next_event:
    #         event = self._next_event.next_event
    #         if event:
    #             return event.event
    #
    # def trigger_next_event(self):
    #     try:
    #         task = self.peek_next_for_event()
    #         if task:
    #             self._task = task.pipeline()
    #             self._task.send(self)
    #     except StopIteration:
    #         pass
