from event_pipeline.executors.hadoop_event import HadoopEvent
from event_pipeline.base import RetryPolicy


class WordCountEvent(HadoopEvent):
    """Example event that performs word count using Hadoop MapReduce"""

    # Configure retry policy for Hadoop job failures
    retry_policy = RetryPolicy(
        max_attempts=3,
        backoff_factor=1.0,
        max_backoff=60,
        retry_on_exceptions=[ConnectionError],
    )

    # Configure the Hadoop executor
    executor_config = {
        "host": "hadoop-master",
        "port": 8020,
        "username": "hadoop",
        "max_workers": 5,
    }

    def _execute_hadoop(self, input_path: str) -> dict:
        """
        Execute word count job on Hadoop

        Args:
            input_path: HDFS path containing input text files

        Returns:
            Dictionary containing word counts
        """
        # Here you would implement the actual Hadoop MapReduce job
        # This is just a mock implementation
        job_config = {
            "job_name": "word_count",
            "input_path": input_path,
            "output_path": "/tmp/wordcount_output",
            "mapper": "word_count_mapper.py",
            "reducer": "word_count_reducer.py",
        }

        return {
            "job_id": "mock_job_123",
            "status": "COMPLETED",
            "result": {"word1": 10, "word2": 5},
        }
