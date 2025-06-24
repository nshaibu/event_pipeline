import typing
import logging
from abc import ABC, abstractmethod
from .result import EventResult


class ExecutionResultEvaluationStrategyBase(ABC):
    """Abstract base class for task evaluation strategies."""

    @abstractmethod
    def evaluate(self, task_results: typing.List[EventResult]) -> bool:
        """
        Evaluate whether the event should be considered successful.

        Args:
            task_results: List of individual task results

        Returns:
            bool: True if the event meets the success criteria
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return a human-readable name for this strategy."""
        pass


class AllTasksMustSucceedStrategy(ExecutionResultEvaluationStrategyBase):
    """Event succeeds only if ALL tasks succeed."""

    def evaluate(self, task_results: typing.List[EventResult]) -> bool:
        if not task_results:
            return False  # No tasks means no success
        return all(result.success for result in task_results)

    def get_strategy_name(self) -> str:
        return "All Tasks Must Succeed"


class AnyTaskMustSucceedStrategy(ExecutionResultEvaluationStrategyBase):
    """Event succeeds if ANY task succeeds."""

    def evaluate(self, task_results: typing.List[EventResult]) -> bool:
        if not task_results:
            return False  # No tasks means no success
        return any(result.success for result in task_results)

    def get_strategy_name(self) -> str:
        return "Any Task Must Succeed"


class MajorityTasksMustSucceedStrategy(ExecutionResultEvaluationStrategyBase):
    """Event succeeds if majority of tasks succeed."""

    def __init__(self, tie_breaker: bool = True):
        """
        Args:
            tie_breaker: What to return when exactly 50% succeed (for even number of tasks)
        """
        self.tie_breaker = tie_breaker

    def evaluate(self, task_results: typing.List[EventResult]) -> bool:
        if not task_results:
            return False

        successful_count = sum(1 for result in task_results if result.success)
        total_count = len(task_results)

        if successful_count > total_count / 2:
            return True
        elif successful_count < total_count / 2:
            return False
        else:
            # Exactly 50% - use tie breaker
            return self.tie_breaker

    def get_strategy_name(self) -> str:
        return f"Majority Must Succeed (tie_breaker={self.tie_breaker})"


class MinimumSuccessThresholdStrategy(ExecutionResultEvaluationStrategyBase):
    """Event succeeds if at least N tasks succeed."""

    def __init__(self, minimum_successes: int):
        if minimum_successes < 0:
            raise ValueError("minimum_successes must be non-negative")
        self.minimum_successes = minimum_successes

    def evaluate(self, task_results: typing.List[EventResult]) -> bool:
        if not task_results and self.minimum_successes == 0:
            return True

        successful_count = sum(1 for result in task_results if result.success)
        return successful_count >= self.minimum_successes

    def get_strategy_name(self) -> str:
        return f"At Least {self.minimum_successes} Tasks Must Succeed"


class PercentageSuccessThresholdStrategy(ExecutionResultEvaluationStrategyBase):
    """Event succeeds if at least X% of tasks succeed."""

    def __init__(self, success_percentage: float):
        if not 0 <= success_percentage <= 100:
            raise ValueError("success_percentage must be between 0 and 100")
        self.success_percentage = success_percentage

    def evaluate(self, task_results: typing.List[EventResult]) -> bool:
        if not task_results:
            return self.success_percentage == 0

        successful_count = sum(1 for result in task_results if result.success)
        actual_percentage = (successful_count / len(task_results)) * 100
        return actual_percentage >= self.success_percentage

    def get_strategy_name(self) -> str:
        return f"At Least {self.success_percentage}% Must Succeed"


class NoFailuresAllowedStrategy(ExecutionResultEvaluationStrategyBase):
    """Event succeeds if NO tasks fail (but allows empty task list)."""

    def evaluate(self, task_results: typing.List[EventResult]) -> bool:
        # Empty list is considered success (no failures)
        return all(result.success for result in task_results)

    def get_strategy_name(self) -> str:
        return "No Failures Allowed"
