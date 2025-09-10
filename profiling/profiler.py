import cProfile
import os
import pstats
from pathlib import Path
from pstats import SortKey

from command_line_flags import PipelineType, args
from pipelines import (BatchPipeline, DecisionTreePipeline, LinearPipeline,
                       ParallelPipeline)

if __name__ == "__main__":

    match args.type:
        case PipelineType.LINEAR.value:
            pipeline = LinearPipeline(["Kwabena"], 30)
        case PipelineType.DECISION_TREE.value:
            pipeline = DecisionTreePipeline(["Kwabena"], 30)
        case PipelineType.PARALLEL.value:
            pipeline = ParallelPipeline(["Kwabena"], 30)
        case PipelineType.BATCH.value:
            pipeline = BatchPipeline(["Kwabena"], 30)
        case _:
            pipeline = LinearPipeline(["Kwabena"], 30)


    cProfile.run("pipeline.start()", str(Path("profiling", "stats.txt")))

    p = pstats.Stats(str(Path("profiling", "stats.txt")))

    p.sort_stats(SortKey.CUMULATIVE).print_stats(
        "event_pipeline"
    ).strip_dirs().dump_stats(str(Path("profiling", "stats.prof")))

    if args.run_in_web_browser:
        os.system("snakeviz" + str(Path(" profiling", "stats.prof")))
