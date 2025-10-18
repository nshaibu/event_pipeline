from typing import Tuple

from nexus import EventBase


class EventOne(EventBase):
    def process(self, name, age) -> Tuple[bool, str]:
        print("EventOne")
        print("I am " + name[0] + " and I am " + str(age) + " years old")
        return True, "EventOne"


# TODO: consider adding a flag that would decide whether event two fails or not
class EventTwo(EventBase):
    def process(self, name, age) -> Tuple[bool, str]:
        print("EventTwo")
        print("I am " + name[0] + " and I am " + str(age) + " years old")
        return True, "EventTwo"


class EventTwoWithPipeResults(EventBase):
    def process(self, name, age) -> Tuple[bool, str]:
        previous_result = self.previous_result.first().content  # type:ignore
        print("EventTwo")
        print("Previous result is " + previous_result)
        print("I am " + name[0] + " and I am " + str(age) + " years old")
        return True, "EventTwo"


class EventThree(EventBase):
    def process(self) -> Tuple[bool, str]:
        print("Previous event failed")
        return True, "EventThree"


class EventFour(EventBase):
    def process(self) -> Tuple[bool, str]:
        print("Previous event didn't failed")
        return True, "EventFour"
