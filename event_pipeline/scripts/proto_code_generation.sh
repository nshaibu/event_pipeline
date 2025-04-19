#!/usr/bin/env bash

project_root=../protos
python_code_dir=../protos
proto_script_path=../protos/task.proto

python -m grpc_tools.protoc -I${project_root} \
--python_out=${python_code_dir} \
--pyi_out=${python_code_dir} \
--grpc_python_out=${python_code_dir} ${proto_script_path}
