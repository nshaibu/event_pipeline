import logging
from .base import PipelineExecutorMixinBase, ExecutorType
from ..utils import coroutine, build_event_arguments_from_pipeline_param
from ..exceptions import (
    EventDoesNotExist,
    EventNotConfigured,
    EventDone,
)

PipelineParam = object()

logger = logging.getLogger(__name__)


class PipelineCoroutineEventExecutorMixin(PipelineExecutorMixinBase):
    executor_type = ExecutorType.COROUTINE

    @classmethod
    @coroutine
    def dispatch_event(cls):
        pipeline_param: PipelineParam = (yield)

        if not pipeline_param.is_configured():
            raise EventNotConfigured("Pipeline not configured yet")

        pipeline_event = pipeline_param.move_to_next()
        if pipeline_event is None:
            raise EventDone("Event done")

        try:
            event_init_arguments, event_call_arguments = (
                build_event_arguments_from_pipeline_param(
                    pipeline_event.event, pipeline_param
                )
            )

            event_init_arguments = event_init_arguments or {}
            event_call_arguments = event_call_arguments or {}

            if pipeline_event.is_conditional:
                event_params = pipeline_event.event_params or {}
                for sub_event in event_params:
                    init_arguments, _ = build_event_arguments_from_pipeline_param(
                        sub_event, pipeline_param
                    )
                    init_arguments = init_arguments or {}
                    event_init_arguments.update(init_arguments)

                event_init_arguments["event_params"] = pipeline_event.event_params

            event = pipeline_event.event(**event_init_arguments)
            response = event(**event_call_arguments)
            if response["status"] == 1:
                pipeline_param.trigger_next_event()
            else:
                task_error = TrackGenicError(
                    message=response,
                    lot_number=pipeline_param.lot_number,
                    oid_string=pipeline_param.oid_string,
                )
                pipeline_event.errors.append(task_error)

            # copy the rest of the errors
            if hasattr(event, "_errors"):
                pipeline_event.errors.extend(event._errors)
        except (KeyError, ValueError, AttributeError) as e:
            task_error = TrackGenicError(
                message={"status": 0, "message": str(e)},
                lot_number=pipeline_param.lot_number,
                oid_string=pipeline_param.oid_string,
                exception=e,
            )
            pipeline_event.errors.append(task_error)
        except GS1EventDone:
            logger.info("Task finished")
        except GeneratorExit:
            logger.warning("Task exited")
