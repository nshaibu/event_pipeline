import typing
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from event_pipeline.task import PipelineTask, PipelineTaskGrouping
    from event_pipeline.pipeline import Pipeline


class ExecutionPlan:
    task_profiles: typing.List[typing.Union["PipelineTask", "PipelineTaskGrouping"]]
    pipeline: typing.Optional["Pipeline"]
