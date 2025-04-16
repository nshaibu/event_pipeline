import unittest
import pytest
from treelib import Tree
from event_pipeline import EventBase
from event_pipeline import Pipeline
from event_pipeline.exceptions import EventDone, EventDoesNotExist
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

        with pytest.raises(ValueError):
            self.pipeline_klass(name="name", csv_file="none.file")

        with pytest.raises(TypeError):
            self.pipeline_klass()

    def test_pipeline_start(self):
        pipe = self.pipeline_klass(name="test_name")
        try:
            pipe.start()
        except EventDone:
            self.fail("Pipeline raised EventDone unexpectedly!")

    def test_pipeline_shutdown(self):
        pipe = self.pipeline_klass(name="test_name")
        pipe.start()
        try:
            pipe.shutdown()
        except Exception as e:
            self.fail(f"Pipeline shutdown raised an exception: {e}")

    def test_pipeline_stop(self):
        pipe = self.pipeline_klass(name="test_name")
        pipe.start()
        try:
            pipe.stop()
        except Exception as e:
            self.fail(f"Pipeline stop raised an exception: {e}")

    def test_pipeline_get_cache_key(self):
        pipe = self.pipeline_klass(name="test_name")
        cache_key = pipe.get_cache_key()
        self.assertEqual(cache_key, f"pipeline_{pipe.__class__.__name__}_{pipe.id}")

    def test_pipeline_get_task_by_id_invalid(self):
        pipe = self.pipeline_klass(name="test_name")
        with pytest.raises(EventDoesNotExist):
            pipe.get_task_by_id("invalid_id")

    def test_pipeline_get_pipeline_tree(self):
        pipe = self.pipeline_klass(name="test_name")
        tree = pipe.get_pipeline_tree()
        self.assertIsNotNone(tree)
        self.assertTrue(isinstance(tree, Tree))

    def test_pipeline_draw_ascii_graph(self):
        pipe = self.pipeline_klass(name="test_name")
        try:
            pipe.draw_ascii_graph()
        except Exception as e:
            self.fail(f"Drawing ASCII graph raised an exception: {e}")

    @pytest.mark.skip(reason="Not implemented yet")
    def test_pipeline_load_class_by_id(self):
        pipe = self.pipeline_klass(name="test_name")
        cache_key = pipe.get_cache_key()
        loaded_pipe = self.pipeline_klass.load_class_by_id(cache_key)
        self.assertIsNotNone(loaded_pipe)
        self.assertEqual(loaded_pipe.get_cache_key(), cache_key)

    @classmethod
    def tearDownClass(cls):
        del cls.M
        del cls.N
        del cls.pipeline_klass
