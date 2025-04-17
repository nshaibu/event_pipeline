from event_pipeline import EventBase
from event_pipeline.executors.rpc_executor import RPCExecutor


class ComputeTask(EventBase):
    # Configure the executor with remote server details
    executor = RPCExecutor
    executor_config = {
        "host": "localhost",
        "port": 8990,
        "timeout": 30,
        "max_workers": 4,
        "use_encryption": False
    }

    def process(self, x: int) -> tuple[bool, int]:
        # Heavy computation to be executed on remote server
        result = sum(i * i for i in range(x))
        return True, result