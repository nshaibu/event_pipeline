from event_pipeline.manager.remote_manager import RemoteTaskManager
from event_pipeline.manager.rpc_manager import XMLRPCManager
from event_pipeline.manager.grpc_manager import GRPCManager

from examples import broadcast


if __name__ == '__main__':
    with GRPCManager("localhost", port=8990) as manager:
        manager.auto_load_all_task_modules()
        manager.register_task_module("broadcast", broadcast)
        manager.start()
