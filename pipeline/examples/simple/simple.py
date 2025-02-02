from pipeline.pipeline import Pipeline
from pipeline.fields import InputDataField


class Simple(Pipeline):
    name = InputDataField(data_type=str)
