from event_pipeline.manager.remote import RemoteTaskManager

from examples import broadcast

with RemoteTaskManager("localhost", port=8990) as manager:
    manager.auto_load_all_task_modules()
    manager.register_task_module("broadcast", broadcast)
    # manager.start()
