import typing

from pipeline.base import EventBase


class Fetch(EventBase):

    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        print("Executed fetch event")
        return True, "Executed fetch event"
