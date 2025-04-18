#!/usr/bin/env bash

python -m grpc_tools.protoc -I./event_pipeline/protos \
--python_out=././event_pipeline/protos \
--pyi_out=./event_pipeline/protos \
--grpc_python_out=./event_pipeline/protos ./event_pipeline/protos/task.proto
