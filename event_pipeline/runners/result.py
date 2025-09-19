import asyncio
import typing

from event_pipeline.result import ResultSet
from event_pipeline.result_evaluators import (
    EventEvaluationResult,
    EventEvaluator,
    ExecutionResultEvaluationStrategyBase,
)


class ResultProcessor:
    """Handles result processing and aggregation"""

    def __init__(self, evaluator: EventEvaluator):
        self._evaluator = evaluator

    @classmethod
    async def process_futures(
        cls, futures: typing.List[asyncio.Future]
    ) -> typing.Tuple[ResultSet, ResultSet]:
        """Process futures and handle exceptions consistently"""
        results = ResultSet()
        errors = ResultSet()

        for result in await asyncio.gather(*futures, return_exceptions=True):
            try:
                if isinstance(result, Exception):
                    errors.add(result)
                else:
                    results.add(result)
            except Exception as e:
                errors.add(e)

        return results, errors

    def evaluate_execution(
        self,
        results: ResultSet,
        strategy: typing.Optional[ExecutionResultEvaluationStrategyBase] = None,
    ) -> EventEvaluationResult:
        """Evaluate execution results using specified strategy"""
        old_strategy = None
        if strategy is not None:
            old_strategy = self._evaluator.strategy
            self._evaluator.change_strategy(strategy)

        evaluation_result = self._evaluator.evaluate(results)
        if old_strategy:
            self._evaluator.change_strategy(old_strategy)
        return evaluation_result
