import typing

from event_pipeline import EventBase


class Serialise(EventBase):

    def process(self, *args, **kwargs):
        print("Serialization")
        return True, "Serialise"


class Upload(EventBase):

    def process(self, *args, **kwargs):
        print("Upload event")
        return True, "Upload Event"


class Commission(EventBase):

    def process(self, *args, **kwargs):
        print("Commission")
        return True, "Commission"


class Pack(EventBase):

    def process(self, *args, **kwargs):
        print("pack")
        return True, "Pack"


class Ship(EventBase):

    def process(self, *args, **kwargs):
        print("Ship")
        return True, "Ship"


class Unpack(EventBase):

    def process(self, *args, **kwargs):
        print("Unpack")
        return True, "Unpack"


class Receive(EventBase):

    def process(self, *args, **kwargs):
        print("Receive")
        return True, "Receive"


class Dispense(EventBase):

    def process(self, *args, **kwargs):
        print("Dispense")
        return True, "Dispense"
