import asyncio
import typing
from concurrent.futures import Future as MpFuture
from event_pipeline.result import EventResult, ResultSet


class ResultProcessor:
    """Handles result processing and aggregation"""

    def __init__(self, evaluator_factory: "EvaluatorFactory"):
        self._evaluator_factory = evaluator_factory

    async def process_futures(self, futures: typing.List[asyncio.Future]) -> ResultSet:
        """Process futures and handle exceptions consistently"""
        results = ResultSet([])
        errors = []

        for result in await asyncio.gather(*futures, return_exceptions=True):
            try:
                results.add(result)
            except Exception as e:
                errors.append(e)

        return results

    def evaluate_execution(
        self, results: ProcessedResults, strategy: EvaluationStrategy
    ) -> EvaluationResult:
        """Evaluate execution results using specified strategy"""
        evaluator = self._evaluator_factory.create(strategy)
        return evaluator.evaluate(results)
