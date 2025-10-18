from concurrent.futures import Future

import pytest

from nexus.executors import default_executor


def test_default_executor():
    def func(school):
        return school

    def exception_func():
        raise ValueError

    executor = default_executor.DefaultExecutor()
    future = executor.submit(func, "knust")
    assert isinstance(future, Future)
    assert future.result() == "knust"

    with pytest.raises(ValueError):
        executor = default_executor.DefaultExecutor()
        future = executor.submit(exception_func)
        raise future.exception()
