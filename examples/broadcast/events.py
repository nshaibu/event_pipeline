from event_pipeline import EventBase
from event_pipeline.executors.remote_executor import RemoteExecutor
from event_pipeline.executors.grpc_executor import GRPCExecutor


class GeneratorEvent(EventBase):
    executor = GRPCExecutor
    executor_config = {
        "host": "localhost",
        "port": 8990,
    }

    def process(self, name: str):
        return True, name


class ParallelAEvent(EventBase):

    def process(self, *args, **kwargs):
        previous_value = self.previous_result[0].content
        return True, previous_value


class ParallelBEvent(EventBase):

    def process(self, *args, **kwargs):
        previous_value = self.previous_result[0].content
        return True, previous_value


class ParallelCEvent(EventBase):

    def process(self, *args, **kwargs):
        previous_value = self.previous_result[0].content
        return True, previous_value


class PrinterEvent(EventBase):

    def process(self, *args, **kwargs):
        for e in self.previous_result:
            print(f"{e.event_name} -> {e.content}")
        return True, None
