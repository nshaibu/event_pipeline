from unittest import mock
from event_pipeline.utils import (
    generate_unique_id,
    get_function_call_args,
    build_event_arguments_from_pipeline,
    _extend_recursion_depth,
)


def test_generate_unique_id():
    class Klass1:
        pass

    class Klass2:
        pass

    obj1 = Klass1()
    obj2 = Klass1()

    obj3 = Klass2()
    obj4 = Klass1()

    generate_unique_id(obj1)
    generate_unique_id(obj2)
    generate_unique_id(obj3)
    generate_unique_id(obj4)

    assert hasattr(obj1, "_id")
    assert hasattr(obj2, "_id")
    assert hasattr(obj3, "_id")
    assert hasattr(obj4, "_id")

    assert getattr(obj1, "_id") != getattr(obj2, "_id")
    assert getattr(obj3, "_id") != getattr(obj4, "_id")


def test_get_function_call_args():
    params = {"is_config": True, "event": "process"}

    def func_with_no_arguments():
        pass

    def func_with_arguments_but_not_in_params(sh):
        pass

    def func_with_arguments_in_param(is_config, event="event", _complex=True):
        pass

    assert get_function_call_args(func_with_no_arguments, params) == {}
    assert get_function_call_args(func_with_arguments_but_not_in_params, params) == {
        "sh": None
    }
    assert get_function_call_args(func_with_arguments_in_param, params) == {
        "is_config": True,
        "event": "process",
        "_complex": True,
    }


def test_build_event_arguments_from_pipeline():
    from event_pipeline import EventBase, Pipeline
    from event_pipeline.fields import InputDataField

    class A(EventBase):
        def process(self, name, school):
            return True, "Hello world"

    class P(Pipeline):
        name = InputDataField(data_type=str)
        school = InputDataField(data_type=str)

        class Meta:
            pointy = "A"

    p = P(name="nafiu", school="knust")

    assert build_event_arguments_from_pipeline(A, pipeline=p) == (
        {
            "execution_context": None,
            "task_id": None,
            "previous_result": None,
            "stop_on_exception": False,
            "stop_on_success": False,
            "stop_on_error": False,
        },
        {"name": "nafiu", "school": "knust"},
    )


def test__extend_recursion_depth():
    with mock.patch("sys.getrecursionlimit", return_value=1048576):
        assert _extend_recursion_depth() == None

    with mock.patch("sys.getrecursionlimit", return_value=1048576):
        with mock.patch("resource.setrlimit"):
            with mock.patch("sys.setrecursionlimit"):
                assert _extend_recursion_depth(20) == 20
