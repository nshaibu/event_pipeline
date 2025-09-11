import cProfile
import os
import pstats
from pathlib import Path
from pstats import SortKey

from command_line_flags import PipelineType, args
from pipelines import (BatchPipelineType, DecisionTreePipeline, LinearPipeline,
                       LinearPipelineWithPreviousResult, ParallelPipeline)

if __name__ == "__main__":

    name = "Kwabena"
    age = 30

    match args.type:
        case PipelineType.LINEAR.value:
            pipeline = LinearPipeline([name], age)
        case PipelineType.DECISION_TREE.value:
            pipeline = DecisionTreePipeline([name], age)
        case PipelineType.LINEAR_WITH_PREVIOUS_RESULT.value:
            pipeline = LinearPipelineWithPreviousResult([name], age)
        case PipelineType.PARALLEL.value:
            pipeline = ParallelPipeline([name], age)
        case PipelineType.BATCH.value:
            pipeline = BatchPipelineType([name, "Nafiu", "Lateo"], age)
        case _:
            pipeline = LinearPipeline([name], age)

    cProfile.run("pipeline.start()", str(Path("profiling", "stats.txt")))

    p = pstats.Stats(str(Path("profiling", "stats.txt")))

    p.sort_stats(SortKey.CUMULATIVE).print_stats(
        "event_pipeline"
    ).strip_dirs().dump_stats(str(Path("profiling", "stats.prof")))

    if args.run_in_web_browser:
        os.system("snakeviz" + str(Path(" profiling", "stats.prof")))
