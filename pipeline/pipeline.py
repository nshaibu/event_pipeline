class _PipelineMeta(type):

    def __new__(cls, name, bases, attrs, **kwargs):
        pass


class _PipelineState(object):
    pass


class Pipeline(metaclass=_PipelineMeta):
    pass
