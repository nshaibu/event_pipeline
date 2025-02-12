import unittest
import pytest
from event_pipeline import EventBase
from event_pipeline import Pipeline
from event_pipeline.fields import InputDataField, FileInputDataField


class PipelineTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        class M(EventBase):
            def process(self, *args, **kwargs):
                return True, "hello world"

        class N(EventBase):
            def process(self, name):
                return True, name

        class Pipe(Pipeline):
            name = InputDataField(data_type=str, required=True)
            school = InputDataField(data_type=str, default="knust")
            csv_file = FileInputDataField(required=False)

            class Meta:
                pointy = "M->N"

        cls.M = M
        cls.N = N
        cls.pipeline_klass = Pipe

    def test_get_task_by_id(self):
        pipe = self.pipeline_klass(name="text")
        state_b = pipe._state.start.on_success_event

        self.assertIsNotNone(state_b)

        task = pipe.get_task_by_id(state_b.id)
        self.assertIsNotNone(task)
        self.assertEqual(task, state_b)

    def test_get_pipeline_fields(self):
        pipe = self.pipeline_klass(name="text")
        self.assertTrue(
            all(
                [
                    field_name in ["name", "school", "csv_file"]
                    for field_name, _ in pipe.get_fields()
                ]
            )
        )

    def test_pipeline_file_fields(self):
        pipe = self.pipeline_klass(name="name", csv_file="tests/unittests/test_task.py")
        self.assertIsNotNone(pipe.csv_file)

        with pytest.raises(TypeError):
            self.pipeline_klass(name="name", csv_file="none.file")

        with pytest.raises(TypeError):
            self.pipeline_klass()

    @classmethod
    def tearDownClass(cls):
        del cls.M
        del cls.N
        del cls.pipeline_klass
