from event_pipeline import Pipeline
from event_pipeline.fields import InputDataField


class BroadcastPipeline(Pipeline):
    name = InputDataField(data_type=str)

    class Meta:
        pointy = "GeneratorEvent |-> ParallelAEvent || ParallelBEvent || ParallelCEvent |-> PrinterEvent"
