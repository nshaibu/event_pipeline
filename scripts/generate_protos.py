#!/usr/bin/env python
import os
import sys
from grpc_tools import protoc


def generate_grpc_code():
    """Generate gRPC Python code from protocol buffers"""
    proto_dir = os.path.join("event_pipeline", "protos")
    proto_file = os.path.join(proto_dir, "task.proto")

    # Create __init__.py if it doesn't exist
    init_file = os.path.join(proto_dir, "__init__.py")
    if not os.path.exists(init_file):
        open(init_file, "a").close()

    # Generate gRPC code
    protoc.main(
        [
            "grpc_tools.protoc",
            f"--proto_path={proto_dir}",
            f"--python_out={proto_dir}",
            f"--grpc_python_out={proto_dir}",
            proto_file,
        ]
    )


if __name__ == "__main__":
    generate_grpc_code()
