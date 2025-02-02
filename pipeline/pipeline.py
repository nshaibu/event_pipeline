import os
import re
import inspect
import typing
from functools import lru_cache
from .task import PipelineTask


class PipelineState(object):
    def __init__(self, pipeline: PipelineTask):
        self.start: PipelineTask = pipeline
        self.current: PipelineTask = pipeline
        self.next: typing.Optional[PipelineTask] = None


class _PipelineMeta(type):

    def __new__(cls, name, bases, attrs):
        if any(isinstance(base, _PipelineMeta) for base in bases):
            raise Exception

        pointy_path = pointy_str = None

        new_class = super().__new__(name, bases, attrs)
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
                raise
            with open(pointy_file, "r") as f:
                pointy_str = f.read()

        try:
            pipeline = PipelineTask.build_pipeline_from_execution_code(pointy_str)
        except Exception:
            raise

        setattr(new_class, "_state", PipelineState(pipeline))

        return new_class

    @classmethod
    @lru_cache(maxsize=1024)
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
            for _dir in dirs:
                cls.directory_walk(_dir, _dir)


class Pipeline(metaclass=_PipelineMeta):
    pass
