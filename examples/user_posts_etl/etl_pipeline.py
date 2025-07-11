from event_pipeline.pipeline import Pipeline
from event_pipeline.fields import InputDataField
from event_pipeline.signal.signals import pipeline_execution_start
from event_pipeline.decorators import listener
from .events import LoadData, ProcessData, GraphData


class UserPostETLPipeline(Pipeline):
    """
    A pipeline for loading data, processing it, and visualizing it.

    Attributes:
        url (str): The URL of the data to load.

    """

    url = InputDataField(
        data_type=str,
        required=True,
        default="https://jsonplaceholder.typicode.com/posts",
    )

    class Meta:
        pointy = "LoadData |-> ProcessData |-> GraphData"
        # Path to the pointy file, if u choose to execute with it
        # file = "eventpipelines/userspost_ptr.pty"
