import pytest
import unittest
from unittest.mock import patch
from concurrent.futures import ProcessPoolExecutor
from event_pipeline import EventBase
from event_pipeline.base import EventExecutionEvaluationState, EvaluationContext
from event_pipeline.task import PipelineTask
from event_pipeline.decorators import event
from event_pipeline.result import EventResult


class TestEventBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        class WithoutParamEvent(EventBase):
            executor = ProcessPoolExecutor

            def process(self, *args, **kwargs):
                return True, "hello"

        class WithParamEvent(EventBase):
            def process(self, name):
                return True, name

        class ProcessNotImplementedEvent(EventBase):
            pass

        class RaiseErrorEvent(EventBase):
            def process(self, *args, **kwargs):
                raise Exception

        class ProcessReturnFalseEvent(EventBase):
            def process(self, *args, **kwargs):
                return False, "False"

        @event()
        def func_with_no_args():
            return True, "function_with_no_args"

        @event()
        def func_with_args(name):
            return True, name

        cls.WithoutParamEvent = WithoutParamEvent
        cls.WithParamEvent = WithParamEvent
        cls.ProcessNotImplementedEvent = ProcessNotImplementedEvent
        cls.RaiseErrorEvent = RaiseErrorEvent
        cls.func_with_args = func_with_args
        cls.func_with_no_args = func_with_no_args
        cls.ProcessReturnFalseEvent = ProcessReturnFalseEvent

    def test_get_klasses(self):
        klasses = list(EventBase.get_event_klasses())

        self.assertEqual(len(klasses), 7)

    def test_function_base_events_create_class(self):
        task1 = PipelineTask(event=self.func_with_no_args.__name__)
        task2 = PipelineTask(event=self.func_with_args.__name__)

        self.assertTrue(
            issubclass(
                task1.resolve_event_name(self.func_with_no_args.__name__), EventBase
            )
        )
        self.assertTrue(
            issubclass(
                task2.resolve_event_name(self.func_with_args.__name__), EventBase
            )
        )

    def test_is_multiprocssing(self):
        event1 = self.WithParamEvent(None, "1")
        event2 = self.WithoutParamEvent(None, "1")

        self.assertFalse(event1.is_multiprocessing_executor())
        self.assertTrue(event2.is_multiprocessing_executor())

    def test_multiprocess_executor_set_context(self):
        event1 = self.WithoutParamEvent(None, "1")
        event2 = self.WithParamEvent(None, "1")

        self.assertTrue("mp_context" in event1.get_executor_context())
        self.assertTrue("mp_context" not in event2.get_executor_context())

    def test_on_success_and_on_failure_is_called(self):
        event1 = self.WithoutParamEvent(None, "1")
        event2 = self.RaiseErrorEvent(None, "1")
        with patch("event_pipeline.EventBase.on_success") as f:
            event1()
            f.assert_called()

        response = event1()
        self.assertIsInstance(response, EventResult)

        with patch("event_pipeline.EventBase.on_failure") as e:
            event2()
            e.assert_called()

        response = event2()
        self.assertIsInstance(response, EventResult)
        self.assertEqual(response.init_params, event2.get_init_args())
        self.assertEqual(response.call_params, event2.get_call_args())

    def test_instantiate_events_without_process_implementation_throws_exception(self):
        with pytest.raises(TypeError):
            self.ProcessNotImplementedEvent(None, "1")

    def test_event_has_init_and_call_params(self):
        event1 = self.WithParamEvent({"task": 1}, "1", previous_result="box")
        response = event1(name="box")
        self.assertIsInstance(response, EventResult)
        self.assertEqual(response.task_id, "1")
        self.assertEqual(
            response.init_params,
            {
                "execution_context": {"task": 1},
                "task_id": "1",
                "previous_result": "box",
                "stop_on_exception": False,
            },
        )
        self.assertEqual(response.call_params, {"args": (), "kwargs": {"name": "box"}})

    def test_event_flow_branch_to_on_failure_when_process_return_false(self):
        event1 = self.ProcessReturnFalseEvent(None, "1")
        with patch("event_pipeline.EventBase.on_failure") as f:
            event1()
            f.assert_called()


class TestEventExecutionEvaluationState(unittest.TestCase):

    def setUp(self):
        self.success_context_without_errors = {
            "context": EvaluationContext.SUCCESS,
            "result": [EventResult(error=False, content="Success", event_name="test", task_id="test1")],
            "errors": [],
        }

        self.success_context_with_errors = {
            "context": EvaluationContext.SUCCESS,
            "result": [],
            "errors": [Exception("error")],
        }

        self.success_context_with_both_errors_and_results = {
            "context": EvaluationContext.SUCCESS,
            "result": [EventResult(error=False, content="Success", event_name="test", task_id="test2")],
            "errors": [Exception("error")],
        }

        self.error_context_without_errors = {
            "context": EvaluationContext.FAILURE,
            "result": [EventResult(error=False, content="Success", event_name="test", task_id="test3")],
            "errors": [],
        }

        self.error_context_with_errors = {
            "context": EvaluationContext.FAILURE,
            "result": [],
            "errors": [Exception("error")],
        }

        self.error_context_with_both_errors_and_results = {
            "context": EvaluationContext.FAILURE,
            "result": [EventResult(error=False, content="Success", event_name="test", task_id="test4")],
            "errors": [Exception("error")],
        }

    def test_success_context_SUCCESS_ON_ALL_EVENTS_SUCCESS(self):
        self.assertTrue(
            EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS.context_evaluation(
                **self.success_context_without_errors
            )
        )

        self.assertFalse(
            EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS.context_evaluation(
                **self.success_context_with_errors
            )
        )

        self.assertFalse(
            EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS.context_evaluation(
                **self.success_context_with_both_errors_and_results
            )
        )

    def test_success_context_FAILURE_FOR_PARTIAL_ERROR(self):
        self.assertFalse(
            EventExecutionEvaluationState.FAILURE_FOR_PARTIAL_ERROR.context_evaluation(
                **self.success_context_with_errors
            )
        )

        self.assertTrue(
            EventExecutionEvaluationState.FAILURE_FOR_PARTIAL_ERROR.context_evaluation(
                **self.success_context_without_errors
            )
        )

        self.assertFalse(
            EventExecutionEvaluationState.FAILURE_FOR_PARTIAL_ERROR.context_evaluation(
                **self.success_context_with_both_errors_and_results
            )
        )

    def test_success_context_FAILURE_FOR_ALL_EVENTS_FAILURE(self):
        self.assertFalse(
            EventExecutionEvaluationState.FAILURE_FOR_ALL_EVENTS_FAILURE.context_evaluation(
                **self.success_context_with_errors
            )
        )

        self.assertTrue(
            EventExecutionEvaluationState.FAILURE_FOR_ALL_EVENTS_FAILURE.context_evaluation(
                **self.success_context_without_errors
            )
        )

        self.assertTrue(
            EventExecutionEvaluationState.FAILURE_FOR_ALL_EVENTS_FAILURE.context_evaluation(
                **self.success_context_with_both_errors_and_results
            )
        )

    def test_success_context_SUCCESS_FOR_PARTIAL_SUCCESS(self):
        self.assertFalse(
            EventExecutionEvaluationState.SUCCESS_FOR_PARTIAL_SUCCESS.context_evaluation(
                **self.success_context_with_errors
            )
        )

        self.assertTrue(
            EventExecutionEvaluationState.SUCCESS_FOR_PARTIAL_SUCCESS.context_evaluation(
                **self.success_context_without_errors
            )
        )

        self.assertTrue(
            EventExecutionEvaluationState.SUCCESS_FOR_PARTIAL_SUCCESS.context_evaluation(
                **self.success_context_with_both_errors_and_results
            )
        )

    # errors

    def test_error_context_SUCCESS_ON_ALL_EVENTS_SUCCESS(self):
        self.assertFalse(
            EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS.context_evaluation(
                **self.error_context_without_errors
            )
        )

        self.assertTrue(
            EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS.context_evaluation(
                **self.error_context_with_errors
            )
        )

        self.assertTrue(
            EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS.context_evaluation(
                **self.error_context_with_both_errors_and_results
            )
        )

    def test_error_context_FAILURE_FOR_PARTIAL_ERROR(self):
        self.assertTrue(
            EventExecutionEvaluationState.FAILURE_FOR_PARTIAL_ERROR.context_evaluation(
                **self.error_context_with_errors
            )
        )

        self.assertFalse(
            EventExecutionEvaluationState.FAILURE_FOR_PARTIAL_ERROR.context_evaluation(
                **self.error_context_without_errors
            )
        )

        self.assertTrue(
            EventExecutionEvaluationState.FAILURE_FOR_PARTIAL_ERROR.context_evaluation(
                **self.error_context_with_both_errors_and_results
            )
        )

    def test_error_context_FAILURE_FOR_ALL_EVENTS_FAILURE(self):
        self.assertTrue(
            EventExecutionEvaluationState.FAILURE_FOR_ALL_EVENTS_FAILURE.context_evaluation(
                **self.error_context_with_errors
            )
        )

        self.assertFalse(
            EventExecutionEvaluationState.FAILURE_FOR_ALL_EVENTS_FAILURE.context_evaluation(
                **self.error_context_without_errors
            )
        )

        self.assertFalse(
            EventExecutionEvaluationState.FAILURE_FOR_ALL_EVENTS_FAILURE.context_evaluation(
                **self.error_context_with_both_errors_and_results
            )
        )

    def test_error_context_SUCCESS_FOR_PARTIAL_SUCCESS(self):
        self.assertTrue(
            EventExecutionEvaluationState.SUCCESS_FOR_PARTIAL_SUCCESS.context_evaluation(
                **self.error_context_with_errors
            )
        )

        self.assertFalse(
            EventExecutionEvaluationState.SUCCESS_FOR_PARTIAL_SUCCESS.context_evaluation(
                **self.error_context_without_errors
            )
        )

        self.assertFalse(
            EventExecutionEvaluationState.SUCCESS_FOR_PARTIAL_SUCCESS.context_evaluation(
                **self.error_context_with_both_errors_and_results
            )
        )
