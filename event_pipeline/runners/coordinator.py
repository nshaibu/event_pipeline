class ExecutionCoordinator:
    """Coordinates the execution of tasks without managing state directly"""

    def __init__(
        self,
        executor_factory: ExecutorFactory,
        result_processor: ResultProcessor,
        signal_emitter: SignalEmitter,
    ):
        self._executor_factory = executor_factory
        self._result_processor = result_processor
        self._signal_emitter = signal_emitter

    async def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Main execution flow - returns result instead of mutating context"""
        try:
            self._signal_emitter.emit_start(context)

            # Get execution plan
            execution_plan = self._create_execution_plan(context.task_profiles)

            # Execute all tasks
            futures = await self._execute_tasks(execution_plan)

            # Process results
            results = await self._result_processor.process_futures(futures)

            self._signal_emitter.emit_end(context, results)
            return ExecutionResult.success(results)

        except Exception as e:
            self._signal_emitter.emit_error(context, e)
            return ExecutionResult.error(e)

    def _create_execution_plan(self, tasks: list[PipelineTask]) -> ExecutionPlan:
        """Creates execution plan without side effects"""
        return ExecutionPlan.from_tasks(tasks)
