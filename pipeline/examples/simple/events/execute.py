import typing
from concurrent.futures import ProcessPoolExecutor
from pipeline.base import EventBase


class Execute(EventBase):
    # executor = ProcessPoolExecutor

    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        print("Executed execute event")
        return True, "Executed execute event"
