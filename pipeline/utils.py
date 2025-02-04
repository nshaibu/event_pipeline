import typing
import logging
import time
import uuid
import sys
import resource
from functools import wraps
from collections import OrderedDict
from inspect import signature, Signature

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from treelib.tree import Tree

logger = logging.getLogger(__name__)

PipelineParam = object()

from concurrent.futures import Executor


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


def _parse_call_arguments(sign: Signature, pipeline_param: PipelineParam):
    param_dict = OrderedDict()
    init_params = sign.parameters
    for param in init_params.values():
        if param.name != "self":
            param_dict[param.name] = getattr(pipeline_param, param.name, None)
    return param_dict


def build_event_arguments_from_pipeline_param(
    event_klass: typing.Type["EventBase"], pipeline_param: PipelineParam
) -> typing.Tuple[typing.Dict[str, typing.Any], typing.Dict[str, typing.Any]]:
    init_param = None
    call_param = None
    try:
        init_signature = signature(event_klass.__init__)
        init_param = _parse_call_arguments(init_signature, pipeline_param)
    except (ValueError, KeyError) as e:
        logger.warning(
            f"Parsing {event_klass} for initialization parameters failed {str(e)}"
        )

    try:
        init_signature = signature(event_klass.__call__)
        call_param = _parse_call_arguments(init_signature, pipeline_param)
    except (ValueError, KeyError, AttributeError) as e:
        logger.warning(f"Parsing {event_klass} for call parameters failed {str(e)}")

    return init_param, call_param
