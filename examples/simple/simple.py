from event_pipeline.pipeline import Pipeline, BatchPipeline
from event_pipeline.fields import InputDataField
from event_pipeline.signal.signals import pipeline_execution_start
from event_pipeline.decorators import listener


class Simple(Pipeline):
    name = InputDataField(data_type=list, batch_size=5)


class SimpleBatch(BatchPipeline):
    pipeline_template = Simple


# @listener(pipeline_execution_start, sender=Simple)
# def simple_listener(**kwargs):
#     print(kwargs)
