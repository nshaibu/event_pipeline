import typing
import weakref
import logging
import threading
from inspect import Signature, Parameter
from event_pipeline.utils import FakeLock


logger = logging.getLogger(__name__)


class SoftSignal(object):

    def __init__(self, provide_args=None):
        if provide_args is None:
            provide_args = []
        elif not isinstance(provide_args, (list, tuple)):
            provide_args = tuple(provide_args)

        self._provide_args = set(provide_args)
        if "sender" not in self._provide_args:
            self._provide_args.add("sender")

        if "signal" not in self._provide_args:
            self._provide_args.add("signal")

        self.lock = threading.Lock()

        self._emit_signature = self._construct_listener_arguments()

        # Initialize a dict to hold connected listeners as weak references
        self._listeners: typing.Dict[typing.Any, typing.Set[weakref.ReferenceType]] = {}

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("lock")
        state["lock"] = FakeLock()
        return state

    def __setstate__(self, state):
        state["lock"] = threading.Lock()
        self.__dict__.update(state)

    def _construct_listener_arguments(self):
        params = [
            Parameter(
                name=name,
                annotation=typing.Any,
                kind=Parameter.KEYWORD_ONLY,
            )
            for name in self._provide_args
        ]
        return Signature(params)

    def emit(
        self, sender: typing.Any, **kwargs
    ) -> typing.List[typing.Tuple[typing.Any, typing.Any]]:
        """
        Emit a signal to all connected listeners for a given sender.

        Args:
            sender: The object sending the signal.
            **kwargs: Additional keyword arguments to pass to listeners.
        Return:
            A list of tuples containing (listener, response).
        """
        responses = []
        if sender in self._listeners:
            for weak_listener in self._listeners[sender]:
                listener = weak_listener()  # Get the listener from the weak reference
                if listener:  # Check if the listener is still alive
                    bounded_args = self._emit_signature.bind(
                        signal=self, sender=sender, **kwargs
                    )
                    try:
                        response = listener(**bounded_args.kwargs)
                    except Exception as e:
                        logger.exception(str(e), exc_info=e)
                        response = e
                    responses.append((listener, response))

        return responses

    def clean(self, sender: typing.Any) -> None:
        """
        Clean up all listeners associated with the sender.

        Args:
            sender: The object whose listeners should be removed.
        """
        with self.lock:
            if sender in self._listeners:
                del self._listeners[sender]

    def connect(self, sender: typing.Any, listener) -> None:
        """
        Connect a listener to a sender.

        Args:
            sender: The object sending the signal.
            listener: The function to be called when the signal is emitted.
        """
        if sender not in self._listeners:
            self._listeners[sender] = set()

        ref = weakref.ref
        listener_obj = listener
        if hasattr(listener, "__self__") and hasattr(listener, "__func__"):
            ref = weakref.WeakMethod
            listener_obj = listener.__self__

        ref_listener = ref(listener)

        with self.lock:
            self._listeners[sender].add(ref_listener)

        # remove the reference when the referent is garbage collected
        weakref.finalize(
            listener_obj,
            self._remove_unalived_listener,
            sender=sender,
            listener=ref_listener,
        )

    def disconnect(self, sender: typing.Any, listener: typing.Callable) -> None:
        """
        Disconnect a listener from a sender.

        Args:
            sender: The object sending the signal.
            listener: The function to be removed from the signal's listeners.
        """
        with self.lock:
            if sender in self._listeners:
                self._listeners[sender] = set(
                    [
                        weak_listener
                        for weak_listener in self._listeners[sender]
                        if weak_listener() != listener
                    ]
                )
                # Clean up the list if it is empty
                if not self._listeners[sender]:
                    del self._listeners[sender]

    def _remove_unalived_listener(self, sender, listener: typing.Any = None) -> None:
        if sender:
            with self.lock:
                if sender in self._listeners:
                    try:
                        self._listeners[sender].remove(listener)
                    except KeyError:
                        pass


pipeline_pre_init = SoftSignal(provide_args=["cls", "args", "kwargs"])
pipeline_post_init = SoftSignal(provide_args=["pipeline"])


pipeline_shutdown = SoftSignal(provide_args=["pipeline", "execution_context"])
pipeline_stop = SoftSignal(provide_args=["pipeline", "execution_context"])


pipeline_execution_start = SoftSignal(provide_args=["pipeline"])
pipeline_execution_end = SoftSignal(provide_args=["execution_context"])


event_init = SoftSignal(provide_args=["event", "init_kwargs"])

event_execution_init = SoftSignal(
    provide_args=["event", "execution_context", "executor", "call_kwargs"]
)
event_execution_start = SoftSignal(provide_args=["event", "execution_context"])
event_execution_end = SoftSignal(provide_args=["event", "execution_context"])
event_execution_retry = SoftSignal(
    provide_args=[
        "event",
        "execution_context",
        "task_id",
        "backoff",
        "retry_count",
        "max_attempts",
    ]
)
event_execution_retry_done = SoftSignal(
    provide_args=["event", "execution_context", "task_id", "max_attempts"]
)
event_execution_cancelled = SoftSignal(
    provide_args=["task_profiles", "execution_context", "state"]
)
event_execution_aborted = SoftSignal(
    provide_args=["task_profiles", "execution_context", "state"]
)


DEFAULT_SIGNALS = [
    event_execution_init,
    event_execution_start,
    event_execution_end,
    event_execution_retry_done,
    event_execution_retry,
]
