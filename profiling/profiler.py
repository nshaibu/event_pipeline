import cProfile
import os
import sys
import argparse
import pstats
import snakeviz.stats
from pstats import SortKey

from command_line_flags import PipelineType, cmd_parser
from pipelines import (
    BatchPipelineType,
    DecisionTreePipeline,
    LinearPipeline,
    LinearPipelineWithPreviousResult,
    ParallelPipeline,
)

def profile_metrics_to_html(profile_file_name: str, output_html_file_name: str) -> None:
    """
    Convert profiling metrics to HTML using snakeviz.
    Args:
        profile_file_name (str): The name of the profiling file.
        output_html_file_name (str): The name of the output HTML file.
    Returns:
        None
    """
    stats = pstats.Stats(profile_file_name)
    data = snakeviz.stats.get_profile_data(stats)
    template = snakeviz.stats.get_template()
    html_output = template.render(data=data)
    with open(output_html_file_name, 'w') as f:
        f.write(html_output)


name = "Kwabena"
age = 30

if __name__ == "__main__":
    try:
        args = cmd_parser.parse_args(sys.argv[1:])
    except argparse.ArgumentError as e:
        print(f"Argument parsing error: {e}")
        sys.exit(1)
    except SystemExit:
        print("Exiting program due to argument parsing issue.")
        sys.exit(1)

    execution_type = args.type
    stats_prof_file = args.output_file
    run_in_web_browser = args.run_in_web_browser
    input_prof_file = args.input_prof_file
    html_report = args.html_report
    
    if stats_prof_file is None:
        stats_prof_file = "profile_results.prof"

    pipeline_constructors = {
        PipelineType.LINEAR.value: lambda: LinearPipeline([name], age),
        PipelineType.DECISION_TREE.value: lambda: DecisionTreePipeline([name], age),
        PipelineType.LINEAR_WITH_PREVIOUS_RESULT.value: lambda: LinearPipelineWithPreviousResult(
            [name], age
        ),
        PipelineType.PARALLEL.value: lambda: ParallelPipeline([name], age),
        PipelineType.BATCH.value: lambda: BatchPipelineType(
            [name, "Nafiu", "Lateo"], age
        ),
    }
    
    if execution_type == "html_report":
        if input_prof_file is None:
            print("Input .prof file must be specified for HTML report generation.")
            sys.exit(1)
        
        if html_report is None:
            print("HTML report flag must be set to generate HTML report.")
            sys.exit(1)
            
        profile_metrics_to_html(input_prof_file, html_report)
        print(f"HTML report generated: {html_report}")
        sys.exit(0)

    pipeline = pipeline_constructors.get(
        execution_type, lambda: LinearPipeline([name], age)
    )()
    
    cProfile.run("pipeline.start()", stats_prof_file)

    p = pstats.Stats(stats_prof_file)

    p.sort_stats(SortKey.CUMULATIVE).print_stats(
        "nuxes"
    ).strip_dirs().dump_stats(stats_prof_file)

    if run_in_web_browser:
        os.system("snakeviz " + stats_prof_file)

    sys.exit(0)
