from nexus import Pipeline
from nexus.fields import InputDataField


class BroadcastPipeline(Pipeline):
    name = InputDataField(data_type=str)

    class Meta:
        pointy = "GeneratorEvent |-> ParallelAEvent || ParallelBEvent || ParallelCEvent |-> PrinterEvent"
