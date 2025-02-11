import typing
import unittest
from unittest.mock import patch
from event_pipeline import EventBase
from event_pipeline.task import PipelineTask


class TestTask(unittest.TestCase):

    def setUp(self):
        pass

    @classmethod
    def setUpClass(cls):
        class A(EventBase):
            def process(self, *args, **kwargs):
                return True, "hello world"

        class B(EventBase):
            def process(self, name):
                return True, name

        cls.A = A
        cls.B = B

    def test_build_event_pipeline(self):
        pass
