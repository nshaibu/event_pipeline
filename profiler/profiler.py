import cProfile
from typing import Tuple

from event_pipeline import EventBase, Pipeline
from event_pipeline.decorators import listener
from event_pipeline.fields import InputDataField
from event_pipeline.pipeline import BatchPipeline, Pipeline
from event_pipeline.signal.signals import pipeline_execution_start


class TestPipeline(Pipeline):
    name = InputDataField(data_type=list)
    age = InputDataField(data_type=int)

class EventOne(EventBase):
    def process(self)-> Tuple[bool, str]:
        print("EventOne")
        return True, "EventOne"
    
class EventTwo(EventBase):
    def process(self)-> Tuple[bool, str]:
        print("EventTwo")
        return True, "EventTwo"
 


if __name__ == "__main__":
    pipeline = TestPipeline(['Kwabena'], 30)
    cProfile.run("pipeline.start()")
