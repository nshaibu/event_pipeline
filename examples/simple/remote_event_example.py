from event_pipeline.executors.remote_event import RemoteEvent
from event_pipeline.executors.remote_executor import RemoteExecutor
from event_pipeline.base import ExecutorInitializerConfig


class DataProcessingEvent(RemoteEvent):
    """Example remote event that processes data on a remote server"""

    # Configure the remote executor
    executor_config = ExecutorInitializerConfig(
        host="remote-server.example.com",
        port=12345,
        timeout=60,
        use_encryption=True,
        client_cert_path="/path/to/client.crt",
        client_key_path="/path/to/client.key",
        ca_cert_path="/path/to/ca.crt",
    )

    def _execute_remote(self, data: dict, *args, **kwargs) -> dict:
        """
        Process data on remote server.
        This method will be executed on the remote server.
        """
        # Example processing logic
        result = {
            "processed": True,
            "input_size": len(data),
            "output": {
                key: value.upper() if isinstance(value, str) else value
                for key, value in data.items()
            },
        }
        return result


# Example usage:
if __name__ == "__main__":
    from event_pipeline.executors.remote_executor import RemoteTaskManager
    import threading

    # Start remote task manager in background thread
    manager = RemoteTaskManager(
        host="0.0.0.0",
        port=12345,
        cert_path="/path/to/server.crt",
        key_path="/path/to/server.key",
        ca_certs_path="/path/to/ca.crt",
        require_client_cert=True,
    )
    server_thread = threading.Thread(target=manager.start)
    server_thread.daemon = True
    server_thread.start()

    # Create and execute remote event
    event = DataProcessingEvent(
        execution_context={},  # Add your execution context here
        task_id="data-processing-1",
    )

    # Process data remotely
    input_data = {"name": "test", "value": 42}

    success, result = event.process(input_data)
    print(f"Success: {success}")
    print(f"Result: {result}")
