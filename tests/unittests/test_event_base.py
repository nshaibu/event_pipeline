import typing
import unittest
from unittest.mock import patch
from concurrent.futures import ProcessPoolExecutor

import pytest

from event_pipeline import EventBase
from event_pipeline.task import PipelineTask
from event_pipeline.decorators import event
from event_pipeline.constants import EventResult


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

    def test_get_klasses(self):
        klasses = list(EventBase.get_event_klasses())

        self.assertEqual(len(klasses), 6)

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

    def test_instantiate_events_without_process_implementation_throws_exception(self):
        with pytest.raises(TypeError):
            self.ProcessNotImplementedEvent(None, "1")

    def test_event_has_init_and_call_params(self):
        event1 = self.WithParamEvent({"task": 1}, "1", previous_result="box")
        response = event1(name="box")
        self.assertIsInstance(response, EventResult)
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
