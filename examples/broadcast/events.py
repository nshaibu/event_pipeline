from event_pipeline import EventBase


class GeneratorEvent(EventBase):

    def process(self, name: str):
        return True, name


class ParallelAEvent(EventBase):

    def process(self, *args, **kwargs):
        previous_value = self.previous_result[0].detail
        return True, previous_value


class ParallelBEvent(EventBase):

    def process(self, *args, **kwargs):
        previous_value = self.previous_result[0].detail
        return True, previous_value


class ParallelCEvent(EventBase):

    def process(self, *args, **kwargs):
        previous_value = self.previous_result[0].detail
        return True, previous_value


class PrinterEvent(EventBase):

    def process(self, *args, **kwargs):
        for e in self.previous_result:
            print(f"{e.event_name} -> {e.detail}")
        return True, None
