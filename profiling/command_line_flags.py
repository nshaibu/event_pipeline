import argparse
from enum import Enum

class PipelineType(Enum):
    LINEAR = "linear"
    LINEAR_WITH_PREVIOUS_RESULT = "linear_pr"
    DECISION_TREE = "decision_tree"
    PARALLEL = "parallel"
    BATCH = "batch"


parser = argparse.ArgumentParser(description="Process event pipeline with flags")
parser.add_argument(
    "-t",
    "--type",
    type=str,
    default=PipelineType.LINEAR.value,
    help="This is the type of pipeline that's being run, whether a linear,decision_tree, parallel or batch",
)
parser.add_argument(
    "-w",
    "--run_in_web_browser",
    type=bool,
    default=False,
    help="This is the type of pipeline that's being run, whether a linear,decision_tree, parallel or batch",
)
parser.add_argument(
    "-o",
    "--output_file",
    default=None,
    help="The output file path for the profiler"
)


args = parser.parse_args()
