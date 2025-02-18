from unittest import TestCase
from event_pipeline.constants import EMPTY
from event_pipeline.exceptions import MultiValueError
from event_pipeline.result import EventResult, ResultSet


class TestEventResultSet(TestCase):

    def setUp(self):
        class EventValue(object):
            def __init__(self, start):
                self.start = start

        self.r1 = EventResult(
            error=True,
            task_id="tast1",
            event_name="test_1",
            content="Hello World!",
            init_params={"a": 1},
            call_params={"b": 2},
        )
        self.r_1 = EventResult(
            error=False, task_id="tast1", event_name="test_1", content="Hello World!"
        )
        self.r2 = EventResult(
            error=True,
            task_id="tast2",
            event_name="test_2",
            content={1, 2, 4, 5},
            init_params={"a": 1},
            call_params={"b": 2},
        )
        self.r3 = EventResult(
            error=False, task_id="tast3", event_name="test_3", content=(1, 2, 4, 5)
        )
        self.r4 = EventResult(
            error=False, task_id="tast4", event_name="test_4", content=[1, 2, 4, 5]
        )
        self.r5 = EventResult(
            error=False,
            task_id="tast5",
            event_name="test_5",
            content=EventValue("1"),
            call_params={"b": 2},
            content_processor=lambda x: {"start": x.start},
        )
        self.r6 = EventResult(
            error=True,
            task_id="test_6",
            event_name="test_6",
            content={"a": 1},
            call_params={"b": 2},
        )

        self.rs1 = ResultSet([self.r1, self.r2, self.r_1])
        self.rs2 = ResultSet([self.r3, self.r4])
        self.rs3 = ResultSet([self.r5, self.r6])

        self.EventValue = EventValue

    def test_event_result_data_type_detection(self):
        self.assertEqual(self.r1.get_content_type(), str)
        self.assertEqual(self.r2.get_content_type(), set)
        self.assertEqual(self.r3.get_content_type(), tuple)
        self.assertEqual(self.r4.get_content_type(), list)
        self.assertEqual(self.r5.get_content_type(), self.EventValue)
        self.assertEqual(self.r6.get_content_type(), dict)

    def test_event_call_and_init_param(self):
        self.assertEqual(self.r1.init_params, {"a": 1})
        self.assertEqual(self.r1.call_params, {"b": 2})

        self.assertIs(self.r3.init_params, EMPTY)
        self.assertIs(self.r3.call_params, EMPTY)

    def test_event_result_serialization(self):
        serialized_dict = self.r1.as_dict()

        self.assertIsInstance(serialized_dict, dict)
        self.assertEqual(serialized_dict["error"], self.r1.error)
        self.assertEqual(serialized_dict["task_id"], self.r1.task_id)
        self.assertEqual(serialized_dict["event_name"], self.r1.event_name)
        self.assertEqual(serialized_dict["content"], self.r1.content)

        serialized_dict1 = self.r5.as_dict()

        self.assertIsInstance(serialized_dict1, dict)
        self.assertEqual(serialized_dict1["error"], self.r5.error)
        self.assertEqual(serialized_dict1["task_id"], self.r5.task_id)
        self.assertEqual(serialized_dict1["event_name"], self.r5.event_name)
        self.assertEqual(serialized_dict1["content"], {"start": self.r5.content.start})

    def test_result_set_contains_event_result(self):
        self.assertEqual(len(self.rs1), 3)
        self.assertEqual(len(self.rs2), 2)
        self.assertEqual(len(self.rs3), 2)

        self.assertTrue(self.r1 in self.rs1)
        self.assertTrue(self.r2 in self.rs1)

        self.assertTrue(self.r3 in self.rs2)
        self.assertTrue(self.r4 in self.rs2)

        self.assertTrue(self.r5 in self.rs3)
        self.assertTrue(self.r6 in self.rs3)

    def test_result_set_filter(self):
        # test filter by id
        qs = self.rs1.filter(id=self.r1.id)
        self.assertIsInstance(qs, ResultSet)
        self.assertEqual(len(qs), 1)
        self.assertEqual(qs[0].task_id, self.r1.task_id)
        self.assertEqual(qs.first(), self.r1)

        # filter by other fields
        qs = self.rs1.filter(task_id=self.r1.task_id)

        self.assertIsInstance(qs, ResultSet)
        self.assertEqual(len(qs), 2)
        self.assertTrue(all(r.task_id == self.r1.task_id for r in qs))

    def test_result_set_getting_a_single_result(self):
        with self.assertRaises(MultiValueError):
            self.rs1.get(task_id=self.r1.task_id)

        with self.assertRaises(IndexError):
            self.rs1.get(task_id="not_a_task_id")

        result = self.rs1.get(task_id=self.r2.task_id)
        self.assertIsInstance(result, EventResult)
        self.assertEqual(result.task_id, self.r2.task_id)

    def test_result_set_can_be_copied(self):
        qs1 = self.rs1.copy()
        self.assertNotEqual(id(qs1), id(self.rs1))
        self.assertEqual(len(qs1), len(self.rs1))
        self.assertTrue(all(result in self.rs1 for result in qs1))

    def test_result_set_discard(self):
        self.assertEqual(len(self.rs1), 3)

        self.rs1.discard(self.r2)

        self.assertEqual(len(self.rs1), 2)
        with self.assertRaises(IndexError):
            self.rs1.get(id=self.r2.id)

    def test_result_set_clear(self):
        self.assertEqual(len(self.rs1), 3)

        self.rs1.clear()
        self.assertEqual(len(self.rs1), 0)

    def test_result_set_contains(self):
        self.assertEqual(len(self.rs1), 3)
        self.assertTrue(self.r1 in self.rs1)
        self.assertFalse(self.r4 in self.rs1)

    def test_result_set_add_event_result(self):
        self.assertEqual(len(self.rs1), 3)

        self.rs1.add(self.r4)
        self.assertEqual(len(self.rs1), 4)

        result = self.rs1.get(id=self.r4.id)
        self.assertIsInstance(result, EventResult)
        self.assertEqual(result.id, self.r4.id)
        self.assertEqual(result.task_id, self.r4.task_id)

        self.rs1.discard(self.r4)

    def test_result_set_does_not_accept_duplicate_event_result(self):
        self.assertEqual(len(self.rs3), 2)

        self.rs1.add(self.r4)
        self.assertEqual(len(self.rs3), 2)

    def test_result_set_can_add_other_result_set(self):
        qs1 = self.rs1.copy()
        qs2 = self.rs2.copy()

        self.assertEqual(len(qs1), 3)
        self.assertEqual(len(qs2), 2)

        qs1.add(qs2)
        self.assertEqual(len(qs1), 5)
        self.assertEqual(len(qs2), 2)

    def test_result_set_get_first_result(self):
        self.assertIsInstance(self.rs3.first(), EventResult)

        qs1 = self.rs1.copy()
        qs1.clear()
        self.assertIsNone(qs1.first())
