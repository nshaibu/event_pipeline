from unittest import TestCase
import time
from event_pipeline.result import ResultSet, EventResult
from event_pipeline.constants import EMPTY
from event_pipeline.exceptions import StopProcessingError

from event_pipeline.base import (
    EventBase,
    RetryPolicy,
    ExecutorInitializerConfig,
    EventExecutionEvaluationState,
    EvaluationContext,
)


class TestRetryPolicy(TestCase):
    def setUp(self):
        self.retry_policy = RetryPolicy(
            max_attempts=3,
            backoff_factor=0.1,
            max_backoff=1.0,
            retry_on_exceptions=[ValueError],
        )

    def test_retry_policy_init(self):
        self.assertEqual(self.retry_policy.max_attempts, 3)
        self.assertEqual(self.retry_policy.backoff_factor, 0.1)
        self.assertEqual(self.retry_policy.max_backoff, 1.0)
        self.assertEqual(self.retry_policy.retry_on_exceptions, [ValueError])

    def test_retry_policy_defaults(self):
        policy = RetryPolicy()
        self.assertIsNotNone(policy.max_attempts)
        self.assertIsNotNone(policy.backoff_factor)
        self.assertIsNotNone(policy.max_backoff)
        self.assertEqual(policy.retry_on_exceptions, [])


class TestExecutorInitializerConfig(TestCase):
    def test_executor_config_init(self):
        config = ExecutorInitializerConfig(
            max_workers=4, max_tasks_per_child=10, thread_name_prefix="test"
        )
        self.assertEqual(config.max_workers, 4)
        self.assertEqual(config.max_tasks_per_child, 10)
        self.assertEqual(config.thread_name_prefix, "test")

    def test_executor_config_defaults(self):
        config = ExecutorInitializerConfig()
        self.assertIs(config.max_workers, EMPTY)
        self.assertIs(config.max_tasks_per_child, EMPTY)
        self.assertIs(config.thread_name_prefix, EMPTY)


class TestEventExecutionEvaluationState(TestCase):
    def setUp(self):
        self.success_result = EventResult(
            error=False, task_id="1", event_name="test", content={}
        )
        self.error_result = EventResult(
            error=True, task_id="2", event_name="test", content={}
        )

    def test_success_on_all_events_success(self):
        state = EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS
        results = ResultSet([self.success_result])
        self.assertTrue(state._evaluate(results, []))

        # Should fail if any errors
        self.assertFalse(state._evaluate(results, [Exception()]))

    def test_failure_for_partial_error(self):
        state = EventExecutionEvaluationState.FAILURE_FOR_PARTIAL_ERROR
        results = ResultSet([self.success_result])

        # Should succeed with no errors
        self.assertFalse(state._evaluate(results, []))

        # Should fail with any error
        self.assertTrue(state._evaluate(results, [Exception()]))

    def test_success_for_partial_success(self):
        state = EventExecutionEvaluationState.SUCCESS_FOR_PARTIAL_SUCCESS
        results = ResultSet([self.success_result])

        # Should succeed with at least one success
        self.assertTrue(state._evaluate(results, [Exception()]))

        # Should fail with no successes
        self.assertFalse(state._evaluate(ResultSet([]), [Exception()]))

    def test_failure_for_all_events_failure(self):
        state = EventExecutionEvaluationState.FAILURE_FOR_ALL_EVENTS_FAILURE

        # Should succeed with any success
        self.assertFalse(
            state._evaluate(ResultSet([self.success_result]), [Exception()])
        )

        # Should fail only if all fail
        self.assertTrue(state._evaluate(ResultSet([]), [Exception()]))

    def test_context_evaluation(self):
        state = EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS
        results = ResultSet([self.success_result])

        # Test success context
        self.assertTrue(
            state.context_evaluation(results, [], context=EvaluationContext.SUCCESS)
        )

        # Test failure context
        self.assertTrue(
            state.context_evaluation(
                results, [Exception()], context=EvaluationContext.FAILURE
            )
        )

        self.assertFalse(
            state.context_evaluation(
                results, [Exception()], context=EvaluationContext.SUCCESS
            )
        )
