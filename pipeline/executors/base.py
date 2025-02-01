class PipelineExecutorMixinBase(object):

    @classmethod
    def receive_event_data(cls, *args, **kwargs):
        raise NotImplementedError

    @classmethod
    def dispatch_event(cls, *args, **kwargs):
        raise NotImplementedError
