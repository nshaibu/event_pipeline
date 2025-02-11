from concurrent.futures import Future
from event_pipeline.executors import default_executor


def test_default_executor():
    def func(school):
        return school

    executor = default_executor.DefaultExecutor()
    future = executor.submit(func, "knust")
    assert isinstance(future, Future)
    assert future.result() == "knust"
