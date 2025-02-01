import typing
import logging
from functools import wraps
from collections import OrderedDict
from inspect import signature, Signature

logger = logging.getLogger(__name__)


def coroutine(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cor = func(*args, **kwargs)
        cor.send(None)
        return cor

    return wrapper


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
