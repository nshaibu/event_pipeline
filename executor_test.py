from event_pipeline.executors.rpc_executor import XMLRPCExecutor


def dummy_task(a: int, b: int) -> int:
    return a + b


with XMLRPCExecutor("localhost", port=8990) as executor:
    future = executor.submit(dummy_task, 20090, 3998)
    print(future.result())
