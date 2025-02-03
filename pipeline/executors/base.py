from enum import Enum, unique


@unique
class ExecutorType(Enum):
    COROUTINE = "coro"
    MULTIPROCESSING = "multi-process"
    ASYNC = "async"


class PipelineExecutorMixinBase(object):
    executor_type: ExecutorType = None

    @classmethod
    def receive_event_data(cls, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def dispatch_event(cls, *args, **kwargs):
        raise NotImplementedError
