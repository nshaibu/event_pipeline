import typing
import logging
from collections import deque
from event_pipeline.typing import TaskType
from event_pipeline.pipeline import Pipeline
from event_pipeline.parser.operator import PipeType
from event_pipeline.exceptions import TaskSwitchingError
from event_pipeline.execution.state_manager import ExecutionStatus
from event_pipeline.execution.context import ExecutionContext

logger = logging.getLogger(__name__)


def run_workflow(
    task: TaskType,
    pipeline: "Pipeline",
    sink_queue: deque,
    previous_context: typing.Optional[ExecutionContext] = None,
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
    # TODO: make this function iterative

    if task:
        if previous_context is None:
            execution_context = ExecutionContext(pipeline=pipeline, task=task)
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

            execution_context = ExecutionContext(
                pipeline=pipeline,
                task=list(parallel_tasks) if parallel_tasks else task,
            )

            execution_context.previous_context = previous_context
            previous_context.next_context = execution_context

        execution_context.dispatch()  # execute task

        execution_state = execution_context.state

        if execution_state.status in [
            ExecutionStatus.CANCELLED,
            ExecutionStatus.ABORTED,
        ]:
            logger.warning(
                f"Task execution terminated due to state '{execution_state.status}'."
                f"\n Skipping task execution..."
            )
            return

        switch_request = execution_state.get_switch_request()

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

            run_workflow(
                task=task_profile,
                pipeline=pipeline,
                previous_context=previous_context,
                sink_queue=sink_queue,
            )
        else:
            evaluation_res = execution_context.evaluate_execution_results()
            if task.is_conditional:
                if not evaluation_res.success:  #  execution_context.execution_failed():
                    run_workflow(
                        task=task.on_failure_event,
                        previous_context=execution_context,
                        pipeline=pipeline,
                        sink_queue=sink_queue,
                    )
                else:
                    run_workflow(
                        task=task.on_success_event,
                        previous_context=execution_context,
                        pipeline=pipeline,
                        sink_queue=sink_queue,
                    )
            else:
                run_workflow(
                    task=task.on_success_event,
                    previous_context=execution_context,
                    pipeline=pipeline,
                    sink_queue=sink_queue,
                )

    else:
        # clear the sink nodes
        while sink_queue:
            task = sink_queue.pop()
            run_workflow(
                task=task,
                previous_context=previous_context,
                pipeline=pipeline,
                sink_queue=sink_queue,
            )
