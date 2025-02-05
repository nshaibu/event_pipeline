import typing

from pipeline.base import EventBase


class Return(EventBase):

    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        print("Executed return event")
        return True, "Executed return event"
