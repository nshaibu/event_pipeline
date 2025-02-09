from event_pipeline.pipeline import Pipeline
from event_pipeline.fields import InputDataField


class Simple(Pipeline):
    name = InputDataField(data_type=str)
