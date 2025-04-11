import typing
import logging
import time
import uuid
import sys

try:
    import resource
except ImportError:
    # No windows support for this lib
    resource = None

from inspect import signature, Parameter, isgeneratorfunction, isgenerator

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from .exceptions import ImproperlyConfigured
from .constants import EMPTY, BATCH_PROCESSOR_TYPE

if typing.TYPE_CHECKING:
    from .base import EventBase
    from .pipeline import Pipeline

logger = logging.getLogger(__name__)


def _extend_recursion_depth(limit: int = 1048576):
    """
    Extends the maximum recursion depth of the Python interpreter.

    Args:
        limit: The new recursion depth limit. Defaults to 1048576.

    This function adjusts the system’s recursion limit to allow deeper recursion
    in cases where the default limit might cause a RecursionError.
    """
    if resource is None:
        return
    rec_limit = sys.getrecursionlimit()
    if rec_limit == limit:
        return
    try:
        resource.setrlimit(resource.RLIMIT_STACK, (limit, resource.RLIM_INFINITY))
        sys.setrecursionlimit(limit)
    except Exception as e:
        logger.error(f"Extending system recursive depth failed. {str(e)}")
        return e
    return limit


def generate_unique_id(obj: object):
    """
    Generate unique identify for objects
    :param obj: The object to generate the id for
    :return: string
    """
    pk = getattr(obj, "_id", None)
    if pk is None:
        pk = f"{obj.__class__.__name__}-{time.time()}-{str(uuid.uuid4())}"
        setattr(obj, "_id", pk)
    return pk


def build_event_arguments_from_pipeline(
    event_klass: typing.Type["EventBase"], pipeline: "Pipeline"
) -> typing.Tuple[typing.Dict[str, typing.Any], typing.Dict[str, typing.Any]]:
    """
    Builds the event arguments by extracting necessary data from the pipeline
    for a given event class.

    Args:
        event_klass: The class of the event (subclass of EventBase) for which
                     the arguments are being constructed.
        pipeline: The Pipeline object containing the data required to build
                  the event arguments.

    Returns:
        A tuple of two dictionaries:
            - The first dictionary contains the primary event arguments.
            - The second dictionary contains additional or optional event arguments.
    """
    return get_function_call_args(
        event_klass.__init__, pipeline
    ), get_function_call_args(event_klass.process, pipeline)


def get_function_call_args(
    func, params: typing.Union[typing.Dict[str, typing.Any], "Pipeline", object]
) -> typing.Dict[str, typing.Any]:
    """
    Extracts the arguments for a function call from the provided parameters.

    Args:
        func: The function for which arguments are to be extracted.
        params: A dictionary of parameters or a Pipeline object containing
                the necessary arguments for the function.

    Returns:
        A dictionary where the keys are the function argument names
        and the values are the corresponding argument values.
    """
    params_dict = {}
    try:
        sig = signature(func)
        for param in sig.parameters.values():
            if param.name != "self":
                value = (
                    params.get(param.name, param.default)
                    if isinstance(params, dict)
                    else getattr(params, param.name, param.default)
                )
                if value is not EMPTY and value is not Parameter.empty:
                    params_dict[param.name] = value
                else:
                    params_dict[param.name] = None
    except (ValueError, KeyError) as e:
        logger.warning(f"Parsing {func} for call parameters failed {str(e)}")

    for key in ["args", "kwargs"]:
        if key in params_dict and params_dict[key] is None:
            params_dict.pop(key, None)
    return params_dict


class AcquireReleaseLock(object):
    """A context manager for acquiring and releasing locks."""

    def __init__(self, lock):
        self.lock = lock

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, *args):
        self.lock.release()


def validate_batch_processor(batch_processor: BATCH_PROCESSOR_TYPE) -> bool:
    if not callable(batch_processor):
        raise ValueError(f"Batch processor '{batch_processor}' must be callable")

    sig = signature(batch_processor)
    if not sig.parameters or len(sig.parameters) != 2:
        raise ImproperlyConfigured(
            f"Batch processor '{batch_processor.__name__}' must have at least two arguments"
        )

    required_field_names = ["values", "batch_size", "chunk_size"]
    batch_kwarg = {}  # this is only use during the test

    for field_name, parameter in sig.parameters.items():
        if field_name == "chunk_size" or field_name == "batch_size":
            batch_kwarg[field_name] = 2
            if parameter.default is not Parameter.empty:
                if not isinstance(parameter.default, (int, float)):
                    raise ImproperlyConfigured(
                        f"Batch processor '{batch_processor.__name__}' argument 'batch_size/chunk_size' "
                        f"must have a default value type of int or float "
                    )
        if field_name not in required_field_names:
            raise ImproperlyConfigured(
                f"Batch processor '{batch_processor.__name__}' arguments must fields named {required_field_names}. "
                f"{field_name} cannot be use"
            )

    try:
        obj = batch_processor([1], **batch_kwarg)
        return (
            isinstance(obj, typing.Iterable)
            or isgeneratorfunction(obj)
            or isgenerator(obj)
        )
    except Exception as e:
        raise ImproperlyConfigured("Batch processor error") from e


def get_expected_args(
    func: typing.Callable, include_type: bool = False
) -> typing.Dict[str, typing.Any]:
    """
    Get the expected arguments of a function as a dictionary where the keys are argument names
    and the values are their default values (if any).

    Args:
        func (Callable): The function to inspect.
        include_type (bool): Whether the return type is expected.
    Returns:
        Dict[str, Any]: A dictionary with argument names as keys and default values (or `None` if no default) as values.
    """
    sig = signature(func)
    args_dict = {}

    for param_name, param in sig.parameters.items():
        if param.name == "self":
            continue
        if param.default is Parameter.empty:
            args_dict[param_name] = (
                param.annotation if include_type else Parameter.empty.__name__
            )
        else:
            args_dict[param_name] = param.annotation if include_type else param.default

    return args_dict


def get_obj_state(obj: typing.Any) -> typing.Dict[str, typing.Any]:
    try:
        return obj.get_state()
    except (AttributeError, NotImplementedError):
        return obj.__getstate__()


def get_obj_klass_import_str(obj: typing.Any) -> str:
    return f"{obj.__class__.__module__}.{obj.__class__.__qualname__}"
