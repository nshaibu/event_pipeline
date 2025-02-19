import typing
import weakref
import logging
import threading


logger = logging.getLogger(__name__)


class SoftSignal(object):

    def __init__(self, provide_args=None):
        if provide_args is None:
            provide_args = []
        elif not isinstance(provide_args, (list, tuple)):
            provide_args = tuple(provide_args)

        self.provide_args = set(provide_args)

        self.lock = threading.Lock()

        # Initialize a dict to hold connected listeners as weak references
        self._listeners: typing.Dict[typing.Any, typing.Set[weakref.ReferenceType]] = {}

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
                    try:
                        response = listener(signal=self, sender=sender, **kwargs)
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

    def connect(
        self, sender: typing.Any, listener: typing.Callable[[...], typing.Any]
    ) -> None:
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
