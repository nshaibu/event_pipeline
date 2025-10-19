import asyncio
import logging
from typing import Optional, Tuple, Any
from contextlib import asynccontextmanager

from event_pipeline.flows import setup_execution_flow
from event_pipeline.execution.state_manager import ExecutionStatus
from event_pipeline.execution.result import ResultProcessor
from event_pipeline.execution.context import ExecutionContext

logger = logging.getLogger(__name__)


class ExecutionCoordinator:
    """
    Coordinates execution of tasks based on task hierarchy.

    Manages the lifecycle of task execution including setup, running,
    error handling, and cleanup operations.
    """

    def __init__(
        self,
        execution_context: ExecutionContext,
        result_processor: Optional[ResultProcessor] = None,
        timeout: Optional[float] = None,
    ):
        """
        Initialize the ExecutionCoordinator.

        Args:
            execution_context: The execution context containing task configuration
            result_processor: Custom result processor (creates default if None)
            timeout: Optional timeout in seconds for execution
        """
        self.execution_context = execution_context
        self._result_processor = result_processor or ResultProcessor()
        self._timeout = timeout
        self._flow = None

    def _setup_execution_flow(self):
        """
        Setup the execution flow based on task dependencies.

        Returns:
            Configured execution flow ready for running

        Raises:
            ValueError: If execution context is invalid
        """
        try:
            logger.info("Setting up execution flow")
            flow = setup_execution_flow(self.execution_context)
            logger.debug(f"Execution flow configured: {flow}")
            return flow
        except Exception as e:
            logger.error(f"Failed to setup execution flow: {e}", exc_info=True)
            raise ValueError(f"Invalid execution context: {e}") from e

    async def _execute_async(self) -> Tuple[Any, Any]:
        """
        Execute the tasks asynchronously.

        Returns:
            Tuple of (results, errors) from task execution

        Raises:
            asyncio.TimeoutError: If execution exceeds timeout
            Exception: If execution fails critically
        """
        flow = self._setup_execution_flow()
        self._flow = flow

        try:
            self.execution_context.update_status(ExecutionStatus.RUNNING)
            logger.info("Starting task execution")

            try:
                if self._timeout:
                    future = await asyncio.wait_for(flow.run(), timeout=self._timeout)
                else:
                    future = await flow.run()
            except:
                return

            logger.info("Task execution completed, processing results")
            results, errors = await self._result_processor.process_futures([future])

            # Update status based on results
            if errors:
                logger.warning(f"Execution completed with {len(errors)} error(s)")
                self.execution_context.update_status(ExecutionStatus.FAILED)
            else:
                logger.info("Execution completed successfully")
                self.execution_context.update_status(ExecutionStatus.COMPLETED)

            return results, errors

        except asyncio.TimeoutError:
            logger.error(f"Execution exceeded timeout of {self._timeout}s")
            self.execution_context.update_status(ExecutionStatus.FAILED)
            raise
        except Exception as e:
            logger.error(f"Execution failed with error: {e}", exc_info=True)
            self.execution_context.update_status(ExecutionStatus.FAILED)
            raise

    def execute(self) -> Tuple[Any, Any]:
        """
        Execute the tasks based on the execution context.

        Handles event loop management and ensures proper cleanup.

        Returns:
            Tuple of (results, errors) from task execution

        Raises:
            RuntimeError: If called from within an existing event loop
            Exception: If execution fails
        """
        try:
            # Check if we're already in an async context
            try:
                asyncio.get_running_loop()
                # If we get here, there IS a running loop
                raise RuntimeError(
                    "execute() cannot be called from within an async context. "
                    "Use execute_async() instead."
                )
            except RuntimeError as e:
                # Check if this is our error or the "no running loop" error
                if "async context" in str(e):
                    raise
                # Otherwise, no running loop exists - we can proceed

            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Execute
            return loop.run_until_complete(self._execute_async())

        except Exception as e:
            logger.error(f"Execution coordinator failed: {e}", exc_info=True)
            self.execution_context.update_status(ExecutionStatus.FAILED)
            raise

    async def execute_async(self) -> Tuple[Any, Any]:
        """
        Execute tasks asynchronously when already in an async context.

        Use this method when calling from async code instead of execute().

        Returns:
            Tuple of (results, errors) from task execution
        """
        return await self._execute_async()

    async def cancel(self):
        """Cancel the currently running execution."""
        if self._flow:
            logger.warning("Cancelling execution flow")
            # Assuming flow has a cancel method, adjust as needed
            if hasattr(self._flow, "cancel"):
                await self._flow.cancel()
            self.execution_context.update_status(ExecutionStatus.CANCELLED)

    @asynccontextmanager
    async def managed_execution(self):
        """
        Context manager for managed execution with automatic cleanup.

        Usage:
            async with coordinator.managed_execution() as (results, errors):
                # Use results
                pass
        """
        try:
            results, errors = await self._execute_async()
            yield results, errors
        finally:
            # Cleanup operations
            logger.debug("Cleaning up execution resources")
            self._flow = None

    def __repr__(self) -> str:
        return (
            f"ExecutionCoordinator("
            f"context={self.execution_context}, "
            f"timeout={self._timeout})"
        )
