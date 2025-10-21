import typing
import logging
from collections import deque
from event_pipeline.typing import TaskType
from event_pipeline.pipeline import Pipeline

logger = logging.getLogger(__name__)


def execute_task(
    task: "PipelineTask",
    pipeline: "Pipeline",
    sink_queue: deque,
    previous_context: typing.Optional[EventExecutionContext] = None,
):
    """
    Executes a specific task in the pipeline and manages the flow of data.

    Args:
        task: The pipeline task to be executed.
        pipeline: The pipeline object that orchestrates the task execution.
        sink_queue: The queue used to store sink nodes for later processing.
        previous_context: An optional EventExecutionContext containing previous
                          execution context, if available.

    This method performs the necessary operations for executing a task, handles
    task-specific logic, and updates the sink queue with sink nodes for further processing.
    """
    if task:
        if previous_context is None:
            execution_context = EventExecutionContext(pipeline=pipeline, task=task)
            pipeline.execution_context = execution_context
        else:
            if task.sink_node:
                sink_queue.append(task.sink_node)

            parallel_tasks = set()

            # Loop through the chain of tasks, adding each task to the 'parallel_tasks' set,
            # until we encounter a task where the 'on_success_pipe' is no longer equal
            # to PipeType.PARALLELISM.
            # This indicates that the task is part of a parallel execution chain.
            while task and task.on_success_pipe == PipeType.PARALLELISM:
                parallel_tasks.add(task)
                task = task.on_success_event

            if parallel_tasks:
                parallel_tasks.add(task)

            execution_context = EventExecutionContext(
                pipeline=pipeline,
                task=list(parallel_tasks) if parallel_tasks else task,
            )

            with previous_context.conditional_variable:
                execution_context.previous_context = previous_context
                previous_context.next_context = execution_context

        switch_request = execution_context.dispatch()  # execute task

        if execution_context and execution_context.state in [
            ExecutionState.CANCELLED,
            ExecutionState.ABORTED,
        ]:
            logger.warning(
                f"Task execution terminated due to state '{execution_context.state.value}'."
                f"\n Skipping task execution..."
            )
            return

        if switch_request and switch_request.descriptor_configured:
            task_profile = task.get_descriptor(switch_request.next_task_descriptor)
            if task_profile is None:
                logger.warning(
                    f"Task cannot switch to task with the descriptor {switch_request.next_task_descriptor}."
                )
                raise TaskSwitchingError(
                    f"Task cannot switch to task using the descriptor {switch_request.next_task_descriptor}.",
                    params=switch_request,
                    code="task-switching-failed",
                )

            execute_task(
                task=task_profile,
                pipeline=pipeline,
                previous_context=previous_context,
                sink_queue=sink_queue,
            )
        else:
            evaluation_res = execution_context.evaluate_execution_results()
            if task.is_conditional:
                if not evaluation_res.success:  #  execution_context.execution_failed():
                    execute_task(
                        task=task.on_failure_event,
                        previous_context=execution_context,
                        pipeline=pipeline,
                        sink_queue=sink_queue,
                    )
                else:
                    execute_task(
                        task=task.on_success_event,
                        previous_context=execution_context,
                        pipeline=pipeline,
                        sink_queue=sink_queue,
                    )
            else:
                execute_task(
                    task=task.on_success_event,
                    previous_context=execution_context,
                    pipeline=pipeline,
                    sink_queue=sink_queue,
                )

    else:
        # clear the sink nodes
        while sink_queue:
            task = sink_queue.pop()
            execute_task(
                task=task,
                previous_context=previous_context,
                pipeline=pipeline,
                sink_queue=sink_queue,
            )
