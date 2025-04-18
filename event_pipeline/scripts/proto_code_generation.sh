#!/usr/bin/env bash

project_root=./event_pipeline/protos
python_code_dir=./event_pipeline/protos
proto_script_path=./event_pipeline/protos/task.proto

python -m grpc_tools.protoc -I${project_root}\
--python_out=${python_code_dir} \
--pyi_out=${python_code_dir} \
--grpc_python_out=${python_code_dir}
