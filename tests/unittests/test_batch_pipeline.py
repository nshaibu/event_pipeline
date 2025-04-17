import pytest
import unittest
import multiprocessing as mp
from typing import List, Iterator
from unittest.mock import Mock, patch
from event_pipeline import EventBase
from event_pipeline.pipeline import BatchPipeline, Pipeline, BatchPipelineStatus
from event_pipeline.fields import InputDataField
from event_pipeline.exceptions import ImproperlyConfigured


class Start(EventBase):
    def process(self, name, data):
        return True, "Start"


class Process(EventBase):
    def process(self, name, data):
        return True, "Process"


class End(EventBase):
    def process(self, name, data):
        return True, "End"


class DummyPipeline(Pipeline):
    data = InputDataField(data_type=list, batch_size=2)
    name = InputDataField(data_type=str, required=False)

    class Meta:
        pointy = "Start -> Process -> End"


class TestBatchPipeline(unittest.TestCase):
    def setUp(self):
        class TestBatch(BatchPipeline):
            pipeline_template = DummyPipeline

        self.batch_cls = TestBatch

    def test_initialization(self):
        """Test basic initialization of BatchPipeline"""
        batch = self.batch_cls(data=[1, 2, 3, 4], name="test")
        self.assertEqual(batch.data, [1, 2, 3, 4])
        self.assertEqual(batch.name, "test")
        self.assertEqual(batch.status, BatchPipelineStatus.PENDING)
        self.assertIsInstance(batch.lock, mp.synchronize.Lock)
        self.assertEqual(batch.results, [])

    def test_invalid_pipeline_template(self):
        """Test initialization with invalid pipeline template"""

        class InvalidBatch(BatchPipeline):
            pipeline_template = str  # Invalid template

        with self.assertRaises(ImproperlyConfigured):
            InvalidBatch(data=[1, 2])

    def test_batch_processing(self):
        """Test batch processing with multiple items"""
        batch = self.batch_cls(data=[1, 2, 3, 4])
        batch.execute()

        # Check if all pipelines were executed
        self.assertEqual(len(batch._configured_pipelines), 2)  # 2 batches of 2 items
        self.assertEqual(batch.status, BatchPipelineStatus.RUNNING)

    def test_single_pipeline_execution(self):
        """Test execution with single pipeline"""
        batch = self.batch_cls(data=[1])
        batch.execute()

        # Should only create one pipeline
        self.assertEqual(len(batch._configured_pipelines), 1)

    @patch("event_pipeline.pipeline.ProcessPoolExecutor")
    def test_parallel_execution(self, mock_executor):
        """Test parallel execution of multiple pipelines"""
        mock_executor.return_value.__enter__.return_value = Mock()

        batch = self.batch_cls(data=[1, 2, 3, 4, 5, 6])
        batch.execute()

        # Verify ProcessPoolExecutor was used
        mock_executor.assert_called_once()

    def test_custom_batch_processor_with_wrong_call_signature(self):
        """Test custom batch processor method"""

        class WrongBatch(BatchPipeline):
            pipeline_template = DummyPipeline

            def data_batch(self, items: List[int], batch_size: int) -> Iterator[int]:
                for i in range(0, len(items), batch_size):
                    yield items[i : i + batch_size]

        batch = WrongBatch(data=[1, 2, 3, 4])
        with self.assertRaises(ImproperlyConfigured):
            batch._gather_and_init_field_batch_iterators()

    def test_custom_batch_processor(self):
        """Test custom batch processor method"""

        class CustomBatch(BatchPipeline):
            pipeline_template = DummyPipeline

            def data_batch(self, values: List[int], batch_size: int) -> Iterator[int]:
                for i in range(0, len(values), batch_size):
                    yield values[i : i + batch_size]

        batch = CustomBatch(data=[1, 2, 3, 4])
        batch._gather_and_init_field_batch_iterators()

        # Verify custom batch processor was used
        self.assertTrue(
            any(
                field in batch._field_batch_op_map
                for field_name, field in batch.get_fields()
            )
        )

    def test_invalid_batch_processor(self):
        """Test invalid batch processor"""

        class InvalidBatch(BatchPipeline):
            pipeline_template = DummyPipeline

            def data_batch(self, items, batch_size):
                return items  # Not an iterator

        batch = InvalidBatch(data=[1, 2, 3])
        with self.assertRaises(ImproperlyConfigured):
            batch._gather_and_init_field_batch_iterators()

        del batch

    def test_empty_batch(self):
        """Test handling of empty batch"""
        batch = self.batch_cls(data=[])
        with self.assertRaises(Exception):
            batch.execute()
        self.assertEqual(len(batch._configured_pipelines), 0)

    @pytest.mark.skip("Hanging fix it later")
    def test_signal_handling(self):
        """Test signal handling during batch processing"""

        class SignalTestBatch(BatchPipeline):
            pipeline_template = DummyPipeline
            listen_to_signals = ["pipeline_execution_start"]

        batch = SignalTestBatch(data=[1, 2, 3, 4])
        with patch("multiprocessing.Manager") as mock_manager:
            mock_queue = Mock()
            mock_manager.return_value.Queue.return_value = mock_queue
            batch.execute()
            # Verify signal queue was created
            self.assertIsNotNone(batch._signals_queue)

    def tearDown(self):
        # Clean up any resources
        pass
