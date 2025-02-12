import unittest
from event_pipeline import EventBase
from event_pipeline.task import PipelineTask, PipeType


class TestTask(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        class A(EventBase):
            def process(self, *args, **kwargs):
                return True, "hello world"

        class B(EventBase):
            def process(self, name):
                return True, name

        class C(EventBase):
            def process(self, *args, **kwargs):
                return True, self.previous_result

        class S(EventBase):
            def process(self, *args, **kwargs):
                return True, "Sink"

        cls.A = A
        cls.B = B
        cls.C = C
        cls.S = S

    def test_build_event_pipeline_for_line_execution(self):
        p = PipelineTask.build_pipeline_from_execution_code("A->B->C")

        self.assertIsInstance(p, PipelineTask)
        self.assertIsNotNone(p.id)
        self.assertIsInstance(p.on_success_event, PipelineTask)
        self.assertIsInstance(p.on_success_event.on_success_event, PipelineTask)
        self.assertEqual(p.on_success_pipe, PipeType.POINTER)
        self.assertEqual(p.on_success_event.on_success_pipe, PipeType.POINTER)
        self.assertEqual(p.on_success_event.on_success_event.on_success_pipe, None)

    def test_build_event_pipeline_with_result_piping_and_parallel_execution(self):
        p = PipelineTask.build_pipeline_from_execution_code("A||B|->C")

        self.assertIsInstance(p, PipelineTask)
        self.assertEqual(p.on_success_pipe, PipeType.PARALLELISM)
        self.assertEqual(p.on_success_event.on_success_pipe, PipeType.PIPE_POINTER)

    def test_build_event_pipeline_with_conditional_branching(self):
        p = PipelineTask.build_pipeline_from_execution_code("A(0->B,1->C)->S")

        self.assertIsInstance(p, PipelineTask)
        self.assertTrue(p.is_conditional)
        self.assertTrue(p.on_success_event.is_descriptor_task)
        self.assertTrue(p.on_failure_event.is_descriptor_task)
        self.assertIsNotNone(p.sink_node)
        self.assertEqual(p.sink_pipe, PipeType.POINTER)
        self.assertTrue(p.sink_node.is_sink)

    def test_resolve_event_name(self):
        self.assertTrue(issubclass(PipelineTask.resolve_event_name("A"), EventBase))
        self.assertEqual(PipelineTask.resolve_event_name("A"), self.A)

    def test_pointer_to_event(self):
        p = PipelineTask.build_pipeline_from_execution_code("A->B")
        self.assertIsNone(p.get_pointer_type_to_this_event())
        self.assertEqual(p.on_success_event.event, "B")
        self.assertEqual(
            p.on_success_event.get_pointer_type_to_this_event(), PipeType.POINTER
        )

    def test_count_nodes(self):
        p = PipelineTask.build_pipeline_from_execution_code("A->B->C")
        self.assertEqual(p.get_task_count(), 3)
        self.assertEqual(p.get_event_klass(), self.A)

    def test_get_root(self):
        p = PipelineTask.build_pipeline_from_execution_code("A->B->C")
        self.assertEqual(p.on_success_event.on_success_event.get_root().event, "A")

    def test_get_children(self):
        p = PipelineTask.build_pipeline_from_execution_code("A(0->B,1->C)->S")
        p1 = PipelineTask.build_pipeline_from_execution_code("A->B->C")
        self.assertEqual(len(p.get_children()), 3)
        self.assertEqual(len(p1.get_children()), 1)

    @classmethod
    def tearDownClass(cls):
        del cls.A
        del cls.B
        del cls.C
        del cls.S
