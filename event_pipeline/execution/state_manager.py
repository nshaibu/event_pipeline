import typing
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from multiprocessing import Manager, Lock as MPLock
from threading import Lock as ThreadLock
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, Future as MPFuture
from event_pipeline.result import ResultSet, EventResult
from event_pipeline.exceptions import PipelineError

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ABORTED = "aborted"
    FAILED = "failed"


@dataclass
class ExecutionState:
    status: ExecutionStatus = field(default=ExecutionStatus.PENDING)
    errors: typing.List[PipelineError] = field(default_factory=list)
    results: ResultSet[EventResult] = field(default_factory=lambda: ResultSet())

    def to_dict(self) -> dict:
        """Serialize state for IPC"""
        return {
            "status": self.status.value,
            "errors": self.errors,
            "results": self.results,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionState":
        """Deserialize state from IPC"""
        return cls(
            status=ExecutionStatus(data["status"]),
            errors=data["errors"],
            results=data["results"],
        )


class StateManager:

    _instance: typing.Optional["StateManager"] = None
    _instance_lock = ThreadLock()
    _executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)

    def __new__(cls):
        # Thread-safe singleton with double-checked locking
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialize()
                    cls._instance = instance
        return cls._instance

    def _initialize(self):
        """Initialize the manager - called once during singleton creation"""
        self._manager = Manager()

        # Store states in shared dict - direct memory access
        self._states = self._manager.dict()

        # Each state_id gets its own lock
        self._locks = self._manager.dict()

        # Reference counting for safe cleanup
        self._ref_counts = self._manager.dict()

        # Lock to protect state/lock creation
        self._creation_lock = self._manager.Lock()

    @classmethod
    def get_instance(cls) -> "StateManager":
        """Returns the singleton instance."""
        if not cls._instance:
            cls.__new__(cls)
        return cls._instance

    def _run_in_executor(self, func, *args, **kwargs) -> MPFuture:
        """Helper to run a blocking function in the executor."""
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(self._executor, func, *args, **kwargs)

    def create_state(self, state_id: str, initial_state: ExecutionState) -> None:
        """
        Create a new state with its own dedicated lock.
        Thread-safe and idempotent - safe to call multiple times.
        """
        with self._creation_lock:
            if state_id not in self._states:
                self._states[state_id] = initial_state.to_dict()
                self._locks[state_id] = self._manager.Lock()
                self._ref_counts[state_id] = 0

            # Increment reference count
            self._ref_counts[state_id] = self._ref_counts[state_id] + 1

    def get_state(self, state_id: str) -> ExecutionState:
        """
        Retrieve state from shared memory - no pickling overhead.
        """
        if state_id not in self._states:
            raise KeyError(f"State {state_id} not found")
        return ExecutionState.from_dict(self._states[state_id])

    def update_state(self, state_id: str, state: ExecutionState) -> None:
        """
        Update state in shared memory - minimal overhead.
        Must be called within a lock context for thread safety.
        """
        if state_id not in self._states:
            raise KeyError(f"State {state_id} not found")
        self._states[state_id] = state.to_dict()

    def update_status(self, state_id: str, new_status: ExecutionStatus) -> None:
        """
        Optimized status-only update - avoids full state serialization.
        Must be called within a lock context.
        """
        if state_id not in self._states:
            raise KeyError(f"State {state_id} not found")
        state_dict = self._states[state_id]
        state_dict["status"] = new_status.value
        self._states[state_id] = state_dict

    def append_error(self, state_id: str, error: typing.Any) -> None:
        """
        Optimized error append - modifies shared memory directly.
        Must be called within a lock context.
        """
        if state_id not in self._states:
            raise KeyError(f"State {state_id} not found")
        state_dict = self._states[state_id]
        state_dict["errors"].append(error)
        self._states[state_id] = state_dict

    def append_result(self, state_id: str, result: typing.Any) -> None:
        """
        Optimized result append - modifies shared memory directly.
        Must be called within a lock context.
        """
        if state_id not in self._states:
            raise KeyError(f"State {state_id} not found")
        state_dict = self._states[state_id]
        state_dict["results"].append(result)
        self._states[state_id] = state_dict

    @contextmanager
    def acquire(self, state_id: str):
        """
        Context manager for acquiring ONLY this state's lock.
        Other states are completely unaffected.
        """
        if state_id not in self._locks:
            raise KeyError(f"Lock for state {state_id} not found")
        lock = self._locks[state_id]
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    def release_state(self, state_id: str, force: bool = False):
        """
        Decrement reference count and optionally remove state.
        State is only removed when reference count reaches 0 or force=True.
        """
        if state_id not in self._states:
            return

        with self._creation_lock:
            if force:
                self._remove_state_unsafe(state_id)
            else:
                current_count = self._ref_counts.get(state_id, 0)
                if current_count > 0:
                    self._ref_counts[state_id] = current_count - 1

                if self._ref_counts[state_id] == 0:
                    self._remove_state_unsafe(state_id)

    def _remove_state_unsafe(self, state_id: str):
        """Internal method to remove state - must be called within _creation_lock"""
        if state_id in self._states:
            del self._states[state_id]
        if state_id in self._locks:
            del self._locks[state_id]
        if state_id in self._ref_counts:
            del self._ref_counts[state_id]

    def remove_state(self, state_id: str):
        """Clean up state and its dedicated lock"""
        self.release_state(state_id, force=False)

    def get_ref_count(self, state_id: str) -> int:
        """Get the number of active references to a state"""
        return self._ref_counts.get(state_id, 0)

    def get_active_states(self) -> typing.List[str]:
        """Get list of all state_ids in shared memory"""
        return list(self._states.keys())

    def clear_all_states(self):
        """
        Remove all states from shared memory.
        WARNING: Only use this when you're sure no processes are using the states.
        """
        with self._creation_lock:
            self._states.clear()
            self._locks.clear()
            self._ref_counts.clear()

    def shutdown(self):
        """Shuts down the manager's server process."""
        self._manager.shutdown()
        logger.info("StateManager shut down.")

    def __del__(self):
        """Cleanup when manager is destroyed"""
        try:
            if hasattr(self, "_manager"):
                self._manager.shutdown()
        except:
            pass  # Ignore errors during cleanup
