from event_pipeline.executors.rpc_executor import XMLRPCExecutor
from event_pipeline.executors.grpc_executor import GRPCExecutor
from event_pipeline.executors.remote_executor import RemoteExecutor


def dummy_task(a: int, b: int) -> int:
    return a + b


with GRPCExecutor("localhost", port=8990) as executor:
    future = executor.submit(dummy_task, 20090, 3998)
    print(future.result())
