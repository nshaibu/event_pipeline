import asyncio
import typing
from contextlib import contextmanager

from event_pipeline.result import ResultSet
from event_pipeline.result_evaluators import (
    EventEvaluationResult,
    EventEvaluator,
    ExecutionResultEvaluationStrategyBase,
)


class ResultProcessor:
    """Handles result processing and aggregation with configurable evaluation strategies."""

    def __init__(self, evaluator: typing.Optional[EventEvaluator] = None) -> None:
        """
        Initialize the ResultProcessor.

        Args:
            evaluator: Optional event evaluator for result evaluation.
        """
        self._evaluator = evaluator

    def change_strategy(self, evaluator: EventEvaluator) -> "ResultProcessor":
        """
        Change the evaluation strategy.

        Args:
            evaluator: New event evaluator to use.

        Returns:
            Self for method chaining.
        """
        self._evaluator = evaluator
        return self

    @staticmethod
    async def process_futures(
        futures: typing.Sequence[asyncio.Future],
    ) -> typing.Tuple[ResultSet, ResultSet]:
        """
        Process futures and separate successful results from errors.

        Args:
            futures: Sequence of asyncio futures to process.

        Returns:
            Tuple of (successful_results, errors).
        """
        results = ResultSet()
        errors = ResultSet()

        completed = await asyncio.gather(*futures, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                errors.add(result)
            else:
                results.add(result)

        return results, errors

    @contextmanager
    def _temporary_strategy(
        self, strategy: typing.Optional[ExecutionResultEvaluationStrategyBase]
    ) -> typing.Generator[None, None, None]:
        """
        Context manager for temporarily changing evaluation strategy.

        Args:
            strategy: Temporary strategy to use, or None to keep current.

        Yields:
            None
        """
        if strategy is None or self._evaluator is None:
            yield
            return

        original_strategy = self._evaluator.strategy
        try:
            self._evaluator.change_strategy(strategy)
            yield
        finally:
            self._evaluator.change_strategy(original_strategy)

    def evaluate_execution(
        self,
        results: ResultSet,
        strategy: typing.Optional[ExecutionResultEvaluationStrategyBase] = None,
    ) -> EventEvaluationResult:
        """
        Evaluate execution results using the specified or current strategy.

        Args:
            results: ResultSet to evaluate.
            strategy: Optional temporary strategy to use for this evaluation.

        Returns:
            EventEvaluationResult containing the evaluation outcome.

        Raises:
            ValueError: If no evaluator is configured.
        """
        if self._evaluator is None:
            raise ValueError(
                "No evaluator configured. Set an evaluator before calling evaluate_execution."
            )

        with self._temporary_strategy(strategy):
            return self._evaluator.evaluate(results)
