import logging
import typing
from enum import Enum
from apscheduler.schedulers.base import STATE_RUNNING
from apscheduler.schedulers.background import BackgroundScheduler

if typing.TYPE_CHECKING:
    from event_pipeline.pipeline import Pipeline, BatchPipeline

logger = logging.getLogger(__name__)

_PIPELINE_BACKGROUND_SCHEDULER = BackgroundScheduler()


class _PipeLineJob:
    def __init__(
        self,
        pipeline: typing.Union["Pipeline", "BatchPipeline"],
        scheduler: BackgroundScheduler,
    ):
        from event_pipeline.pipeline import BatchPipeline

        super().__init__()
        self._pipeline = pipeline
        self._is_batch = isinstance(pipeline, BatchPipeline)
        self._sched = scheduler

    @property
    def id(self) -> str:
        return self._pipeline.id

    def run(self, *args, **kwargs):
        if self._is_batch:
            self._pipeline.execute()
            return
        self._pipeline.start(force_rerun=True)

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)


class ScheduleMixin:

    class ScheduleTrigger(Enum):
        DATE = "date"
        INTERVAL = "interval"
        CRON = "cron"

    @classmethod
    def get_pipeline_scheduler(cls):
        return _PIPELINE_BACKGROUND_SCHEDULER

    def schedule_job(self, trigger: ScheduleTrigger, **scheduler_kwargs):
        sched = _PIPELINE_BACKGROUND_SCHEDULER
        _job_op = _PipeLineJob(self, sched)

        job = sched.add_job(
            _job_op,
            trigger.value,
            id=_job_op.id,
            name=self.__class__.__name__,
            **scheduler_kwargs,
        )

        if sched.state != STATE_RUNNING:
            sched.start()
        return job
