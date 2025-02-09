import typing

from event_pipeline import EventBase


class SaveToDB(EventBase):

    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        print("Executed save-to-db event")
        return True, "Executed save-to-db event"
