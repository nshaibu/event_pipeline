from event_pipeline import Pipeline
from event_pipeline.fields import InputDataField

class LinearPipeline(Pipeline):
    name = InputDataField(data_type=list)
    age = InputDataField(data_type=int)


class ParallelPipeline(Pipeline):
    name = InputDataField(data_type=list)
    age = InputDataField(data_type=int)


class DecisionTreePipeline(Pipeline):
    name = InputDataField(data_type=list)
    age = InputDataField(data_type=int)


class BatchPipeline(Pipeline):
    name = InputDataField(data_type=list)
    age = InputDataField(data_type=int)


