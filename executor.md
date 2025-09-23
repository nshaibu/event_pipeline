# EventExecutionContext Decomposition Strategy

## Current Problems with EventExecutionContext

The `EventExecutionContext` class violates Single Responsibility Principle by handling:
- Execution coordination
- State management
- Result processing
- Threading synchronization
- Executor management
- Signal emission
- Serialization
- Context linking (doubly-linked list)

## Proposed Decomposition

### 1. Core Data Classes

```python
@dataclass
class ExecutionMetrics:
    """Pure data class for execution timing and statistics"""
    start_time: float
    end_time: float = 0.0
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0.0

@dataclass
class ExecutionState:
    """Immutable execution state"""
    status: ExecutionStatus
    errors: tuple[PipelineError, ...] = ()
    results: ResultSet = field(default_factory=ResultSet)
    
    def with_status(self, status: ExecutionStatus) -> 'ExecutionState':
        return ExecutionState(status, self.errors, self.results)
    
    def with_error(self, error: PipelineError) -> 'ExecutionState':
        return ExecutionState(self.status, self.errors + (error,), self.results)

@dataclass
class ExecutionContext:
    """Core execution data - no behavior, just data"""
    id: str
    task_profiles: list[PipelineTask]
    pipeline: Pipeline
    state: ExecutionState = field(default_factory=lambda: ExecutionState(ExecutionStatus.PENDING))
    metrics: ExecutionMetrics = field(default_factory=lambda: ExecutionMetrics(time.time()))
```

### 2. Execution Coordination

```python
class ExecutionCoordinator:
    """Coordinates the execution of tasks without managing state directly"""
    
    def __init__(self, 
                 executor_factory: ExecutorFactory,
                 result_processor: ResultProcessor,
                 signal_emitter: SignalEmitter):
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
```

### 3. State Management

```python
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
    
    async def transition_to(self, context_id: str, status: ExecutionStatus) -> ExecutionState:
        async with self._lock:
            current = self._states.get(context_id, ExecutionState(ExecutionStatus.PENDING))
            new_state = current.with_status(status)
            self._states[context_id] = new_state
            return new_state
```

### 4. Executor Management

```python
class ExecutorFactory:
    """Creates and configures executors"""
    
    def __init__(self, executor_registry: ExecutorRegistry):
        self._registry = executor_registry
    
    def create_execution_plan(self, tasks: list[PipelineTask]) -> ExecutionPlan:
        """Creates execution plan with proper executor assignments"""
        executor_groups = self._group_tasks_by_executor(tasks)
        return ExecutionPlan(executor_groups)
    
    def _group_tasks_by_executor(self, tasks: list[PipelineTask]) -> dict[ExecutorConfig, list[TaskExecution]]:
        """Groups tasks by their executor requirements"""
        groups = defaultdict(list)
        
        for task in tasks:
            executor_config = self._get_executor_config(task)
            task_execution = self._create_task_execution(task)
            groups[executor_config].append(task_execution)
        
        return dict(groups)

class ExecutorRegistry:
    """Registry for available executors with validation"""
    
    def __init__(self):
        self._executors: dict[str, type[Executor]] = {}
    
    def register(self, name: str, executor_class: type[Executor]) -> None:
        if not issubclass(executor_class, Executor):
            raise ValueError(f"Invalid executor type: {executor_class}")
        self._executors[name] = executor_class
    
    def get(self, name: str) -> type[Executor]:
        if name not in self._executors:
            raise ExecutorNotFound(f"Executor '{name}' not registered")
        return self._executors[name]
```

### 5. Result Processing

```python
class ResultProcessor:
    """Handles result processing and aggregation"""
    
    def __init__(self, evaluator_factory: EvaluatorFactory):
        self._evaluator_factory = evaluator_factory
    
    async def process_futures(self, futures: list[Future]) -> ProcessedResults:
        """Process futures and handle exceptions consistently"""
        results = []
        errors = []
        
        for future in futures:
            try:
                result = await future
                results.append(result)
            except Exception as e:
                error = self._convert_exception_to_error(e)
                errors.append(error)
        
        return ProcessedResults(results, errors)
    
    def evaluate_execution(self, results: ProcessedResults, strategy: EvaluationStrategy) -> EvaluationResult:
        """Evaluate execution results using specified strategy"""
        evaluator = self._evaluator_factory.create(strategy)
        return evaluator.evaluate(results)
```

### 6. Context Chain Management

```python
class ExecutionChain:
    """Manages the chain of execution contexts"""
    
    def __init__(self):
        self._contexts: dict[str, ExecutionContext] = {}
        self._links: dict[str, str] = {}  # context_id -> next_context_id
        self._reverse_links: dict[str, str] = {}  # context_id -> previous_context_id
    
    def add_context(self, context: ExecutionContext, previous_id: str = None) -> None:
        """Add context to chain"""
        self._contexts[context.id] = context
        
        if previous_id:
            self._links[previous_id] = context.id
            self._reverse_links[context.id] = previous_id
    
    def get_chain(self, start_id: str) -> Iterator[ExecutionContext]:
        """Get iterator over execution chain"""
        current_id = start_id
        while current_id:
            yield self._contexts[current_id]
            current_id = self._links.get(current_id)
    
    def filter_by_event(self, event_name: str) -> list[ExecutionContext]:
        """Filter contexts by event name"""
        return [
            ctx for ctx in self._contexts.values()
            if any(task.event == event_name for task in ctx.task_profiles)
        ]
```

### 7. Main Orchestrator

```python
class PipelineExecutor:
    """Main orchestrator that composes all components"""
    
    def __init__(self,
                 coordinator: ExecutionCoordinator,
                 state_manager: ExecutionStateManager,
                 chain_manager: ExecutionChain,
                 signal_emitter: SignalEmitter):
        self._coordinator = coordinator
        self._state_manager = state_manager
        self._chain_manager = chain_manager
        self._signal_emitter = signal_emitter
    
    async def execute_pipeline(self, 
                              tasks: list[PipelineTask], 
                              pipeline: Pipeline,
                              previous_context_id: str = None) -> ExecutionResult:
        """Execute pipeline with proper orchestration"""
        
        # Create execution context
        context = ExecutionContext(
            id=generate_id(),
            task_profiles=tasks,
            pipeline=pipeline
        )
        
        # Add to chain
        self._chain_manager.add_context(context, previous_context_id)
        
        # Update state to executing
        await self._state_manager.transition_to(context.id, ExecutionStatus.EXECUTING)
        
        try:
            # Execute
            result = await self._coordinator.execute(context)
            
            # Update final state
            final_status = ExecutionStatus.FINISHED if result.success else ExecutionStatus.ABORTED
            await self._state_manager.transition_to(context.id, final_status)
            
            return result
            
        except Exception as e:
            await self._state_manager.transition_to(context.id, ExecutionStatus.ABORTED)
            raise
```

## Key Benefits of This Decomposition

### 1. **Single Responsibility**
- Each class has one clear purpose
- Easy to understand and modify
- Testable in isolation

### 2. **Immutability Where Possible**
- `ExecutionState` is immutable
- State changes return new instances
- Reduces threading issues

### 3. **Dependency Injection**
- Components depend on interfaces
- Easy to mock for testing
- Flexible configuration

### 4. **Async/Await Instead of Raw Threading**
- Cleaner concurrency model
- Better error handling
- More predictable execution

### 5. **Clear Separation of Concerns**
- Data classes for data
- Service classes for behavior
- No mixing of concerns

### 6. **Better Error Handling**
- Consistent error types
- Clear error propagation
- No hidden exceptions

## Migration Strategy

### Phase 1: Extract Data Classes
1. Create `ExecutionContext`, `ExecutionState`, `ExecutionMetrics`
2. Update existing code to use new data structures
3. Keep existing behavior intact

### Phase 2: Extract Coordinators
1. Create `ExecutionCoordinator`
2. Move execution logic from old class
3. Update tests

### Phase 3: Extract State Management
1. Create `ExecutionStateManager`
2. Replace manual locking with proper state management
3. Add async support

### Phase 4: Complete Migration
1. Create `PipelineExecutor`
2. Remove old `EventExecutionContext`
3. Update all calling code

## Testing Strategy

```python
# Easy to test individual components
def test_execution_coordinator():
    mock_executor_factory = Mock()
    mock_result_processor = Mock()
    mock_signal_emitter = Mock()
    
    coordinator = ExecutionCoordinator(
        mock_executor_factory,
        mock_result_processor,
        mock_signal_emitter
    )
    
    # Test in isolation
    result = await coordinator.execute(sample_context)
    assert result.success

# Easy to test state transitions
def test_state_manager():
    manager = ExecutionStateManager()
    
    # Test state transitions
    new_state = await manager.transition_to("ctx1", ExecutionStatus.EXECUTING)
    assert new_state.status == ExecutionStatus.EXECUTING
```

This decomposition makes the code much more maintainable, testable, and follows SOLID principles while preserving all the original functionality.