import cProfile
import os
import pstats
from pathlib import Path
from pstats import SortKey

from command_line_flags import PipelineType, args
from pipelines import (
    BatchPipelineType,
    DecisionTreePipeline,
    LinearPipeline,
    LinearPipelineWithPreviousResult,
    ParallelPipeline,
)

if __name__ == "__main__":

    name = "Kwabena"
    age = 30
    stats_txt_file = "profile_results.txt"
    stats_prof_file = "profile_results.prof"
    profiling_dir = "./"

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

    pipeline = pipeline_constructors.get(
        args.type, lambda: LinearPipeline([name], age)
    )()
    cProfile.run("pipeline.start()", str(Path(profiling_dir, stats_txt_file)))

    p = pstats.Stats(str(Path(profiling_dir, stats_txt_file)))

    p.sort_stats(SortKey.CUMULATIVE).print_stats(
        "event_pipeline"
    ).strip_dirs().dump_stats(str(Path(profiling_dir, stats_prof_file)))

    if args.run_in_web_browser:
        os.system("snakeviz" + str(Path(profiling_dir, stats_prof_file)))
