import typing
from concurrent.futures import Future
from event_pipeline.result import EventResult, ResultSet


class ResultProcessor:
    """Handles result processing and aggregation"""

    def __init__(self, evaluator_factory: "EvaluatorFactory"):
        self._evaluator_factory = evaluator_factory

    def process_futures(self, futures: list[Future]) -> ResultSet:
        """Process futures and handle exceptions consistently"""
        results = ResultSet([])
        errors = []

        for future in futures:
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                error = self._convert_exception_to_error(e)
                errors.append(error)

        return ProcessedResults(results, errors)

    def evaluate_execution(
        self, results: ProcessedResults, strategy: EvaluationStrategy
    ) -> EvaluationResult:
        """Evaluate execution results using specified strategy"""
        evaluator = self._evaluator_factory.create(strategy)
        return evaluator.evaluate(results)
