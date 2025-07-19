import asyncio


class ExecutionStateManager:
    """Thread-safe state management"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._states: dict[str, ExecutionState] = {}

    async def get_state(self, context_id: str) -> ExecutionState:
        async with self._lock:
            return self._states.get(context_id, ExecutionState(ExecutionStatus.PENDING))

    async def update_state(self, context_id: str, new_state: ExecutionState) -> None:
        async with self._lock:
            self._states[context_id] = new_state

    async def transition_to(
        self, context_id: str, status: ExecutionStatus
    ) -> ExecutionState:
        async with self._lock:
            current = self._states.get(
                context_id, ExecutionState(ExecutionStatus.PENDING)
            )
            new_state = current.with_status(status)
            self._states[context_id] = new_state
            return new_state
