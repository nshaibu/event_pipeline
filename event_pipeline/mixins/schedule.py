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
        """
        Schedule a pipeline job. There are three triggers used for scheduling a job: cron, date, and interval.

        - cron: CronTrigger: Triggers when current time matches all specified time constraints, similarly to
        how the UNIX cron scheduler works.
            :param int|str year: 4-digit year
            :param int|str month: month (1-12)
            :param int|str day: day of month (1-31)
            :param int|str week: ISO week (1-53)
            :param int|str day_of_week: number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun)
            :param int|str hour: hour (0-23)
            :param int|str minute: minute (0-59)
            :param int|str second: second (0-59)
            :param datetime|str start_date: earliest possible date/time to trigger on (inclusive)
            :param datetime|str end_date: latest possible date/time to trigger on (inclusive)
            :param datetime.tzinfo|str timezone: time zone to use for the date/time calculations
                (defaults to scheduler timezone)
            :param int|None jitter: delay the job execution by ``jitter`` seconds at most

        - date: DateTrigger: Triggers once on the given datetime. If ``run_date`` is left empty, current time is used.
            :param datetime|str run_date: the date/time to run the job at
            :param datetime.tzinfo|str timezone: time zone for ``run_date`` if it doesn't have one already

        - interval: IntervalTrigger: Triggers on specified intervals, starting on ``start_date`` if specified,
        ``datetime.now()`` + interval otherwise.
            :param int weeks: number of weeks to wait
            :param int days: number of days to wait
            :param int hours: number of hours to wait
            :param int minutes: number of minutes to wait
            :param int seconds: number of seconds to wait
            :param datetime|str start_date: starting point for the interval calculation
            :param datetime|str end_date: latest possible date/time to trigger on
            :param datetime.tzinfo|str timezone: time zone to use for the date/time calculations
            :param int|None jitter: delay the job execution by ``jitter`` seconds at most

        :param trigger: Trigger to execute
        :param scheduler_kwargs: Keyword arguments to pass to the scheduler
        :return: Job instance
        """
        sched = self.get_pipeline_scheduler()
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
