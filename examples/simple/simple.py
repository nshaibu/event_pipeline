from nexus.pipeline import Pipeline, BatchPipeline
from nexus.fields import InputDataField
from nexus.signal.signals import pipeline_execution_start
from nexus.decorators import listener


class Simple(Pipeline):
    name = InputDataField(data_type=list, batch_size=5)


class SimpleBatch(BatchPipeline):
    pipeline_template = Simple


@listener(pipeline_execution_start, sender=Simple)
def simple_listener(**kwargs):
    print(kwargs)
