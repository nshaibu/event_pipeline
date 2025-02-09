import typing
from concurrent.futures import ThreadPoolExecutor
from event_pipeline import EventBase


class Fetch(EventBase):
    executor = ThreadPoolExecutor

    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        print("Executed fetch event")
        return True, "Executed fetch event"
