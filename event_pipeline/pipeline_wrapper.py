import os
import time
import typing
from enum import Enum


class PipelineExecutionState(Enum):
    START = "START"
    PROCESS = "PROCESS"
    END = "END"
    FAIL = "FAIL"
    SUCCESS = "SUCCESS"


class PipelineWrapper:
    def __init__(
        self,
        pipeline,
        *,
        focus_on_signals: typing.List[str],
        signals_queue,
        import_string_fn,
        logger,
    ):
        self.pipeline = pipeline
        self.focus_on_signals = focus_on_signals or []
        self.signals_queue = signals_queue
        self._import_string = import_string_fn
        self._logger = logger
        self._connected_signals = []

    def _now(self) -> float:
        return time.time()

    def _emit_lifecycle(
        self,
        state: PipelineExecutionState,
        *,
        error: typing.Optional[str] = None,
        traceback: typing.Optional[str] = None,
    ) -> None:
        message = {
            "type": "pipeline_lifecycle",
            "version": 1,
            "state": state.value,
            "pipeline_id": getattr(self.pipeline, "id", None),
            "process_id": os.getpid(),
            "timestamp": self._now(),
            "error": error,
            "traceback": traceback,
        }

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
        for signal_str in self.focus_on_signals:
            try:
                module = self._import_string(signal_str)
                self._connected_signals.append(module)
            except Exception as e:
                if self._logger:
                    self._logger.warning(
                        f"Signal import failed: {signal_str}, exception: {e}"
                    )

        def signal_handler(*args, **kwargs):
            kwargs = dict(
                **kwargs,
                pipeline_id=getattr(self.pipeline, "id", None),
            )
            signal_data = {
                "args": args,
                "kwargs": kwargs,
            }
            try:
                self.signals_queue.put(signal_data)
            except Exception:
                pass

        for s in self._connected_signals:
            try:
                s.connect(listener=signal_handler, sender=None)
            except Exception:
                pass

    def _disconnect_signals(self) -> None:
        for s in self._connected_signals:
            try:
                s.disconnet(sender=None)
            except Exception:
                pass
        self._connected_signals.clear()

    def run(self):
        pass
