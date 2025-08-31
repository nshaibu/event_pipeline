import os
import time
import typing
from enum import Enum


class PipelineExecutionState(Enum):
    INITIALIZED = "initialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    FINISHED = "finished"


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

    def _connect_signals(self) -> None:
        # Import and connect each requested soft signal so child events are forwared to parent
        if not self.focus_on_signals:
            return

        def signal_handler(*args, **kwargs):
            # todo - convert signal data to Message instance

            # add subprocess context to signal kwargs
            enhanced_kwargs = {
                **kwargs,
                "pipeline_id": getattr(self.pipeline, "id", None),
                "process_id": os.getpid(),
                "timestamp": self._now(),
                "wrapper_id": self.wrapper_id,
            }

            # create message format expected by _BatchProcessingMonitor
            signal_data = {
                "message_type": "pipeline_signal",
                "args": args,
                "kwargs": enhanced_kwargs,
                "wrapper_id": self.wrapper_id,
                "timestamp": self._now(),
                "version": "1",
            }

            try:
                self.signals_queue.put(signal_data)
            except Exception as e:
                if self._logger:
                    self._logger.debug(f"Failed to forward signal: {e}")

        for signal_str in self.focus_on_signals:
            try:
                module = self._import_string(signal_str)
                module.connect(listener=signal_handler, sender=None)
                self._connected_signals.append(module)
                if self._logger:
                    self._logger.debug(f"Connected to signal: {signal_str}")

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
            if self._logger:
                self._logger.debug(
                    f"Starting pipeline execution: {self.pipeline.__class__.__name__}",
                    extra={"pipeline_id": getattr(self.pipeline, "id", None)},
                )

            # execute the pipeline
            execution_context = self.pipeline.start(force_rerun=True)

            if execution_context:
                latest_context = execution_context.get_latest_execution_context()
                if latest_context.execution_failed():
                    # pipeline failed during execution
                    error_node = self.pipeline.get_first_error_execution_node()
                    self.execution_state = PipelineExecutionState.FAILED
                    if self._logger:
                        self._logger.error(
                            f"Pipeline execution failed at task: {error_node.task.id if error_node else 'Unknown'}",
                            extra={
                                "pipeline_id": getattr(self.pipeline, "id", None),
                                "failed_task": error_node.task.id
                                if error_node
                                else None,
                                "execution_state": str(latest_context.state)
                                if latest_context
                                else None,
                            },
                        )
                    return

            self.execution_state = PipelineExecutionState.COMPLETED
            if self._logger:
                self._logger.debug(
                    "Pipeline execution completed successfully",
                    extra={"pipeline_id": getattr(self.pipeline, "id", None)},
                )
        except Exception as e:
            self.exception = e
            self.execution_state = PipelineExecutionState.FAILED

            if self._logger:
                self._logger.error(
                    f"Pipeline execution failed: {e}",
                    exc_info=True,
                    extra={
                        "wrapper_id": self.wrapper_id,
                        "pipeline_id": getattr(self.pipeline, "id", None),
                        "exception_type": type(e).__name__,
                    },
                )

    def _send_wrapper_lifecycle_event(
        self, event_type: str, additional_data: typing.Dict = None
    ) -> None:
        """
        Send wrapper-specific lifecycle events that complement pipeline signals.
        These are processed by _BatchProcessingMonitor but are wrapper-specific, not pipeline signals.
        """
        message_data = {
            "message_type": "wrapper_lifecycle",
            "event_type": event_type,
            "wrapper_id": self.wrapper_id,
            "pipeline_id": getattr(self.pipeline, "id", None),
            "process_id": os.getpid(),
            "timestamp": self._now(),
            "execution_state": self.execution_state.value,
            "version": "1.0",
        }

        if additional_data:
            message_data.update(additional_data)

        try:
            self.signals_queue.put(message_data, timeout=0.5)
        except Exception as e:
            if self._logger:
                self._logger.debug(
                    f"Failed to send wrapper lifecycle event {event_type}: {e}"
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

            # send wrapper started event
            self._send_wrapper_lifecycle_event("wrapper_started")
            if self._logger:
                self._logger.debug(
                    f"Pipeline wrapper started: {self.wrapper_id}",
                    extra={"pipeline_id": getattr(self.pipeline, "id", None)},
                )

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
                "pipeline_state": self._get_pipeline_state_info(),
            }

            self._send_wrapper_lifecycle_event("wrapper_failed", error_data)
            if self._logger:
                self._logger.error(f"Wrapper execution failed: {e}", exc_info=True)
        finally:
            self.end_time = self._now()
            execution_duration = (
                self.end_time - self.start_time if self.start_time else 0
            )
            self.execution_state = PipelineExecutionState.FINISHED

            # Send wrapper finished event with duration
            self._send_wrapper_lifecycle_event(
                "wrapper_finished",
                {
                    "execution_duration": execution_duration,
                    "final_state": self.execution_state.value,
                    "had_exception": self.exception is not None,
                },
            )

            # Cleanup signal connections
            self._disconnect_signals()

            if self._logger:
                self._logger.debug(
                    f"Pipeline wrapper finished: {self.wrapper_id} "
                    f"(Duration: {execution_duration:.2f}s, State: {self.execution_state.value})",
                    extra={"pipeline_id": getattr(self.pipeline, "id", None)},
                )

        return self.pipeline, self.exception
