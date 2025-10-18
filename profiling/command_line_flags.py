import argparse
from enum import Enum


class PipelineType(Enum):
    LINEAR = "linear"
    LINEAR_WITH_PREVIOUS_RESULT = "linear_pr"
    DECISION_TREE = "decision_tree"
    PARALLEL = "parallel"
    BATCH = "batch"


cmd_parser = argparse.ArgumentParser(prog="profiler", description="Process event pipeline with flags", add_help=True)
cmd_parser.add_argument(
    "-t",
    "--type",
    type=str,
    default=PipelineType.LINEAR.value,
    help="This is the type of pipeline that's being run, whether a linear,decision_tree, parallel or batch",
)
cmd_parser.add_argument(
    "-w",
    "--run_in_web_browser",
    type=bool,
    default=False,
    help="This is the type of pipeline that's being run, whether a linear,decision_tree, parallel or batch",
)
cmd_parser.add_argument(
    "-o", "--output_file", type=str, default=None, help="The output file path for the profiler"
)

# arguments for snakeviz HTML report generation
cmd_parser.add_argument(
    "-i", "--input_prof_file", type=str, default=None, help="Input .prof file"
)

cmd_parser.add_argument(
    "-hr", "--html_report", action="store_true", default=None, help="Generate HTML report"
)
