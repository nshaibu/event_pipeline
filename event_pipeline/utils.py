import typing
import logging
import time
import uuid
import sys
import multiprocessing as mp

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
from treelib.tree import Tree
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
        logger.error(f"Extending system recursive depth failed {str(e)}")
        return e
    return limit


class GraphTree(Tree):

    def return_graphviz_data(
        self,
        shape="circle",
        graph="digraph",
        t_filter=None,
        key=None,
        reverse=False,
        sorting=True,
    ) -> str:
        """Exports the tree in the dot format of the graphviz software"""
        nodes, connections = [], []
        if self.nodes:
            for n in self.expand_tree(
                mode=self.WIDTH,
                filter=t_filter,
                key=key,
                reverse=reverse,
                sorting=sorting,
            ):
                nid = self[n].identifier
                state = '"{0}" [label="{1}", shape={2}]'.format(nid, self[n].tag, shape)
                nodes.append(state)

                for c in self.children(nid):
                    cid = c.identifier
                    edge = "->" if graph == "digraph" else "--"
                    connections.append(('"{0}" ' + edge + ' "{1}"').format(nid, cid))

        # write nodes and connections to dot format
        f = StringIO()

        f.write(graph + " tree {\n")
        for n in nodes:
            f.write("\t" + n + "\n")

        if len(connections) > 0:
            f.write("\n")

        for c in connections:
            f.write("\t" + c + "\n")

        f.write("}")

        return f.getvalue()


def generate_unique_id(obj: object):
    """
    Generate unique identify for objects
    :param obj: The object to generate the id for
    :return: string
    """
    pk = getattr(obj, "_id", None)
    if pk is None:
        pk = f"{obj.__class__.__name__}_{time.time()}_{str(uuid.uuid4())}"
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


class FakeLock:
    def __init__(self):
        pass

    def acquire(self, block=True, timeout=-1):
        """Simulate acquiring the lock (actually calling threading lock)."""
        pass

    def release(self):
        """Simulate releasing the lock (actually calling threading lock)."""
        pass

    def __getstate__(self):
        """Return the state for pickling (lock itself is not picklable, so we skip it)."""
        return {}

    def __setstate__(self, state):
        """Restores the lock state (since we're simulating, no need to restore anything)."""
        pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.release()
