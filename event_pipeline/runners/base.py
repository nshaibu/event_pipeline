from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
import time
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class RunnerState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Runner(ABC):
    """Enhanced Runner with state management and hooks"""

    def __init__(self, name: str):
        self.name = name
        self.state = RunnerState.PENDING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.result: Any = None
        self.error: Optional[Exception] = None
        self.context: Dict[str, Any] = {}

        # Hook functions
        self.before_run: Optional[Callable] = None
        self.after_run: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

    @abstractmethod
    def run(self) -> Any:
        """Main execution logic"""
        pass

    def should_run(self) -> bool:
        """Determine if this runner should execute (can be overridden)"""
        return True

    def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the runner with full lifecycle management"""
        if context:
            self.context.update(context)

        if not self.should_run():
            self.state = RunnerState.SKIPPED
            return self._create_result(success=True, skipped=True)

        self.state = RunnerState.RUNNING
        self.start_time = time.time()

        try:
            # Before run hook
            if self.before_run:
                self.before_run(self)

            logger.info(f"Starting {self.name}")
            self.result = self.run()
            self.state = RunnerState.COMPLETED

            # After run hook
            if self.after_run:
                self.after_run(self)

            logger.info(f"Completed {self.name} successfully")
            return self._create_result(success=True)

        except Exception as e:
            self.error = e
            self.state = RunnerState.FAILED

            # Error hook
            if self.on_error:
                self.on_error(self, e)

            logger.error(f"Error in {self.name}: {str(e)}")
            return self._create_result(success=False)

        finally:
            self.end_time = time.time()

    def _create_result(self, success: bool, skipped: bool = False) -> Dict[str, Any]:

        return {
            "success": success,
            "skipped": skipped,
            "result": self.result,
            "duration": self.duration,
            "error": str(self.error) if self.error else None,
            "state": self.state.value,
            "context": self.context.copy(),
        }

    @property
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
