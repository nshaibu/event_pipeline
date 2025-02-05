import typing
import logging
import time
import uuid
import sys
import resource
from functools import wraps
from inspect import signature

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from treelib.tree import Tree

from .constants import EMPTY

logger = logging.getLogger(__name__)

PipelineParam = object()


def _extend_recursion_depth(limit: int = 1048576):
    rec_limit = sys.getrecursionlimit()
    if rec_limit == limit:
        return
    try:
        resource.setrlimit(resource.RLIMIT_STACK, (limit, resource.RLIM_INFINITY))
        sys.setrecursionlimit(limit)
    except Exception as e:
        logger.error(f"Extending system recursive depth failed {str(e)}")


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


def coroutine(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cor = func(*args, **kwargs)
        cor.send(None)
        return cor

    return wrapper


def generate_unique_id(obj: object):
    pk = getattr(obj, "_id", None)
    if pk is None:
        pk = f"{obj.__class__.__name__}_{time.time()}_{str(uuid.uuid4())}"
        setattr(obj, "_id", pk)
    return pk


def build_event_arguments_from_pipeline(
    event_klass: typing.Type["EventBase"], pipeline: "Pipeline"
) -> typing.Tuple[typing.Dict[str, typing.Any], typing.Dict[str, typing.Any]]:
    return get_function_call_args(
        event_klass.__init__, pipeline
    ), get_function_call_args(event_klass.__call__, pipeline)


def get_function_call_args(
    func, params: typing.Union[typing.Dict[str, typing.Any], "Pipeline"]
) -> typing.Dict[str, typing.Any]:
    params_dict = dict()
    try:
        sig = signature(func)
        for param in sig.parameters.values():
            if param.name != "self":
                value = (
                    params.get(param.name)
                    if isinstance(params, dict)
                    else getattr(params, param.name, None)
                )
                if value is not EMPTY:
                    params_dict[param.name] = value
    except (ValueError, KeyError) as e:
        logger.warning(f"Parsing {func} for call parameters failed {str(e)}")

    return params_dict
