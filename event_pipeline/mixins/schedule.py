import logging
import typing
from enum import Enum
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.base import STATE_RUNNING
from apscheduler.schedulers.background import BackgroundScheduler
from event_pipeline.utils import get_function_call_args, get_expected_args
from event_pipeline.exceptions import ValidationError

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

        def tigger_klass(self):
            if self == self.DATE:
                return DateTrigger
            elif self == self.INTERVAL:
                return IntervalTrigger
            else:
                return CronTrigger

    @classmethod
    def get_pipeline_scheduler(cls):
        return _PIPELINE_BACKGROUND_SCHEDULER

    @staticmethod
    def _validate_trigger_args(
        trigger: ScheduleTrigger, trigger_args: typing.Dict[str, typing.Any]
    ):
        klass = trigger.tigger_klass()
        params = get_function_call_args(klass.__init__, trigger_args)
        if not params or not any([params[key] for key in params]):
            expected_args = list(get_expected_args(klass.__init__).keys())
            raise ValidationError(
                message=f"Invalid trigger arguments. Expected argument(s) {expected_args}",
                code="invalid-args",
                params={"trigger_args": trigger_args},
            )

    def schedule_job(self, trigger: ScheduleTrigger, **scheduler_kwargs):
        sched = _PIPELINE_BACKGROUND_SCHEDULER
        _job_op = _PipeLineJob(self, sched)

        self._validate_trigger_args(trigger, scheduler_kwargs)

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
