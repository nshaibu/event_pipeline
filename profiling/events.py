from event_pipeline import EventBase
from typing import Tuple

class EventOne(EventBase):
    def process(self) -> Tuple[bool, str]:
        print("EventOne")
        return True, "EventOne"


class EventTwo(EventBase):
    def process(self) -> Tuple[bool, str]:
        print("EventTwo")
        return True, "EventTwo"



