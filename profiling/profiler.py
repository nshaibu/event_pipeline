import cProfile
import pstats
from pathlib import Path
from pstats import SortKey
from typing import Tuple
import os

from event_pipeline import EventBase, Pipeline
from event_pipeline.decorators import listener
from event_pipeline.fields import InputDataField
from event_pipeline.pipeline import BatchPipeline, Pipeline
from event_pipeline.signal.signals import pipeline_execution_start

#  - Integrate profiling into the event module using `cProfile`.
# - Optionally, use the `telemetry` module to log and track performance data over time.
# - Benchmark critical functions and execution paths within the event module.
# - Document performance metrics (e.g., function call counts, total time, per-call time).
# - Identify any slow-performing code segments or unnecessary overhead.
# - Propose or implement optimisations where applicable.
#

# TODO: think of different scenarios: linear,decision statements, parallel, batch
# build diffrent profilers for the separate scenarios
# build is such that when you run it it gives you a visual view for it
# take a look at the bidirectional operation when the next event doesn't depend on the earlier one
# how do I identify the slowest portions of the code that belong the event pipeline runtime

# have different flags to pass for the diffferent scenarios and the data that is gotten and then how exactly it shows to the person who runs it


class TestPipeline(Pipeline):
    name = InputDataField(data_type=list)
    age = InputDataField(data_type=int)


class EventOne(EventBase):
    def process(self) -> Tuple[bool, str]:
        print("EventOne")
        return True, "EventOne"


class EventTwo(EventBase):
    def process(self) -> Tuple[bool, str]:
        print("EventTwo")
        return True, "EventTwo"


if __name__ == "__main__":
    pipeline = TestPipeline(["Kwabena"], 30)
    cProfile.run("pipeline.start()", str(Path("profiling", "stats.txt")))
    p = pstats.Stats(str(Path("profiling", "stats.txt")))
    p.sort_stats(SortKey.CUMULATIVE).print_stats(
        "event_pipeline"
    ).strip_dirs().dump_stats(str(Path("profiling", "stats.prof")))

    os.system("snakeviz profiling/stats.prof")
