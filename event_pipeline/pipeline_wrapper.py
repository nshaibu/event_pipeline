import dataclasses
import os
import time
import typing
from enum import Enum

from pydantic_mini import Attrib, BaseModel, MiniAnnotated


class PipelineExecutionState(Enum):
    INITIALIZED = "initialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CLEANUP = "cleanup"
    FINISHED = "finished"


class Message(BaseModel):
    message_type: MiniAnnotated[str, Attrib(default="pipeline_lifecycle")]
    version: MiniAnnotated[int, Attrib(default=1)]
    state: MiniAnnotated[str, Attrib(default=None)]
    pipeline_id: int
    process_id: int
    timestamp: MiniAnnotated[time, Attrib(default=time.time())]
    error: MiniAnnotated[typing.Any, Attrib(default=None)]
    extras: MiniAnnotated[dict, Attrib(default_factory=dict)]
    wrapper_id: MiniAnnotated[int, Attrib(default=None)]

    @classmethod
    def from_dict(cls, message_dict: typing.Dict[str, typing.Any]) -> "Message":
        known_fields = {field.name for field in dataclasses.fields(cls)}
        msg = {}
        for field_name, value in message_dict.items():
            if field_name in known_fields:
                msg[field_name] = value
            else:
                if "extras" not in msg:
                    msg["extras"] = {}
                msg["extras"][field_name] = value
        return cls.loads(msg, _format="dict")


class PipelineWrapper:
    def __init__(
        self,
        pipeline,
        *,
        focus_on_signals: typing.List[str],
        signals_queue,
        import_string_fn,
        logger,
        wrapper_id: str = None,
    ):
        self.pipeline = pipeline
        self.focus_on_signals = focus_on_signals or []
        self.signals_queue = signals_queue
        self._import_string = import_string_fn
        self._logger = logger
        self._connected_signals = []
        self.wrapper_id = wrapper_id or f"wrapper_{os.getpid()}_{int(time.time())}"

        self.execution_state = PipelineExecutionState.INITIALIZED
        self.start_time: typing.Optional[float] = None
        self.end_time: typing.Optional[float] = None
        self.exception: typing.Optional[Exception] = None

    def _now(self) -> float:
        return time.time()

    def _emit_lifecycle(
        self,
        state: PipelineExecutionState,
        event_type: str,
        *,
        error: typing.Optional[typing.Any] = None,
        extras: typing.Dict[str, typing.Any] = None,
    ) -> None:
        message: Message = Message(
            message_type=event_type,
            version=1,
            state=state.value,
            pipeline_id=getattr(self.pipeline, "id", None),
            process_id=os.getpid(),
            timestamp=self._now(),
            error=error,
            wrapper_id=self.wrapper_id,
            extras=extras,
        )

        try:
            self.signals_queue.put(message)
        except Exception as e:
            # avoid crashing the subprocess due to IPC issues
            if self._logger:
                self._logger.warning(
                    f"Failed to send lifecycle event {state.value}: {e}"
                )

    def _connect_signals(self) -> None:
        # Import and connect each requested soft signal so child events are forwared to parent
        if not self.focus_on_signals:
            return

        def signal_handler(*args, **kwargs):
            # todo - convert signal data to Message instance
            signal_data = {
                "message_type": "pipeline_signal",
                "wrapper_id": self.wrapper_id,
                "pipeline_id": getattr(self.pipeline, "id", None),
                "process_id": os.getpid(),
                "timestamp": self._now(),
                "args": args,
                "kwargs": dict(**kwargs),
                "version": "1",
            }

            try:
                self.signals_queue.put(signal_data)
            except Exception:
                pass

        for signal_str in self.focus_on_signals:
            try:
                module = self._import_string(signal_str)
                module.connect(listener=signal_handler, sender=None)
                self._connected_signals.append(module)
            except Exception as e:
                if self._logger:
                    self._logger.warning(
                        f"Signal import failed: {signal_str}, exception: {e}"
                    )

    def _disconnect_signals(self) -> None:
        for s in self._connected_signals:
            try:
                s.disconnet(sender=None)
            except Exception as e:
                self._logger.debug(f"Error disconnecting signal: {e}")

        self._connected_signals.clear()

    def _handle_pipeline_execution(self) -> None:
        try:
            self.execution_state = PipelineExecutionState.RUNNING
            self._emit_lifecycle(self.execution_state, "execution_started")

            # execute the pipeline
            execution_context = self.pipeline.start(force_rerun=True)

            if execution_context:
                latest_context = execution_context.get_latest_execution_context()
                if latest_context.execution_failed():
                    # pipeline failed during execution
                    error_node = self.pipeline.get_first_error_execution_node()
                    error_info = {
                        "error_message": "pipeline execution failed",
                        "failed_task_id": error_node.task.id if error_node else None,
                        "execution_context": str(latest_context.state)
                        if latest_context
                        else None,
                    }
                    self.execution_state = PipelineExecutionState.FAILED
                    self._emit_lifecycle(
                        self.execution_state, "execution_failed", error=error_info
                    )

            self.execution_state = PipelineExecutionState.COMPLETED
            self._emit_lifecycle(self.execution_state, "execution_completed")
        except Exception as e:
            self.exception = e
            self.execution_state = PipelineExecutionState.FAILED

            error_data = {
                "error_message": str(e),
                "error_type": type(e).__name__,
                "traceback": self._format_exception_traceback(e),
                "pipeline_state": self._get_pipeline_state_info(),
            }

            self._emit_lifecycle(
                self.execution_state, "execution_failed", error=error_data
            )
            self._logger.error(
                f"Pipeline execution failed: {e}",
                exc_info=True,
                extra={
                    "wrapper_id": self.wrapper_id,
                    "pipeline_id": getattr(self.pipeline, "id", None),
                },
            )

    def _format_exception_traceback(self, exception: Exception) -> str:
        """Format exception with traceback for parent communication"""
        try:
            import traceback

            return "".join(
                traceback.format_exception(
                    type(exception), exception, exception.__traceback__
                )
            )
        except Exception:
            return f"Failed to format traceback for: {str(exception)}"

    def _get_pipeline_state_info(self) -> typing.Dict[str, typing.Any]:
        """Get current pipeline state information for debugging"""
        try:
            return {
                "pipeline_id": getattr(self.pipeline, "id", None),
                "pipeline_class": self.pipeline.__class__.__name__,
                "execution_context_exists": self.pipeline.execution_context is not None,
                "has_cache": bool(getattr(self.pipeline, "_state", None)),
            }
        except Exception:
            return {"error": "Failed to gather pipeline state info"}

    def run(self):
        """
        Execute the pipeline, emitting lifecycle events and returning
        (pipeline, exception) to preserve existing batch behaviour.
        """
        self.start_time = self._now()

        try:
            self.execution_state = PipelineExecutionState.INITIALIZING
            self._emit_lifecycle(self.execution_state, "wrapper_initialized")

            # initialize signals
            self._connect_signals()

            # execute pipeline
            self._handle_pipeline_execution()

        except Exception as e:
            self.exception = e
            self.execution_state = PipelineExecutionState.FAILED

            error_data = {
                "error_message": f"Wrapper execution failed: {str(e)}",
                "error_type": type(e).__name__,
                "traceback": self._format_exception_traceback(e),
            }

            self._emit_lifecycle(
                self.execution_state, "wrapper_failed", error=error_data
            )
            self._logger.error(f"Wrapper execution failed: {e}", exc_info=True)
        finally:
            self._emit_lifecycle(PipelineExecutionState.CLEANUP, "wrapper_cleanup")
            self._disconnect_signals()
            self._emit_lifecycle(PipelineExecutionState.FINISHED, "wrapper_finished")

        return self.pipeline, self.exception
