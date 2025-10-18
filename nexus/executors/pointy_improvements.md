# Pointy Extension v1.1.0

## Event Attributes

Event attributes in the Pointy Extension are designed to be modifiable through the pointy script. The square bracket notation `[]` is used to define attributes for individual events and execution chains during runtime.

An execution chain represents a collection of executable events that share the same execution group. Execution groups are denoted using curly braces `{}`.

**Example:**
```
A[executor="ThreadPoolExecutor", retries=3]
```

In this example, event `A` is configured with a ThreadPoolExecutor and will retry up to 3 times upon failure.

## Grouping and Conditional Execution

The Pointy Extension uses specific symbols to control execution flow:

- **Curly braces `{}`**: Used for grouping events into execution chains
- **Parentheses `()`**: Used for conditional execution logic

Grouping execution directly impacts the processing order by affecting the precedence of instructions within execution chains. This precedence determines how events are scheduled and executed.

**Example:**
```
{A->B}[retries=3] || {B->C}
```

In this configuration:
- The chain `A->B` executes in parallel with the chain `B->C`
- Each event within the `A->B` chain will be retried up to 3 times if it fails
- The parallel execution operator `||` ensures both chains run simultaneously

### Executor Configuration for Groups

When grouping is applied, a single executor can be designated to handle all events within that group by providing the executor parameter at the group level.

**Example:**
```
{A->B}[executor="XMLRPCExecutor", executor_config="{'host':'localhost', 'port':8090}"] -> C
```

In this scenario:
- Events `A` and `B` belong to the same execution chain
- Both events are affected by the shared attribute configurations
- The XMLRPCExecutor with the specified configuration handles both events
- Event `C` executes after the completion of the `A->B` chain

### Individual Event Executors

In situations where no common executor is specified at the group level and each event within a chain has its own executor configuration, the system will use each event's individual executor for execution. This provides flexibility for mixed-executor scenarios within the same chain.

## Parallel Execution Executor Selection

When events participating in a parallel execution chain have their own individual executors, the system follows a specific selection mechanism:

### Selection Rules

1. **Common Executor Priority**: If a common executor is explicitly provided in the pointy script, it takes precedence over individual event executors.
   
   **Example:**
   ```
   A||B[executor="ThreadPoolExecutor"]
   ```

2. **First Compatible Executor**: When no common executor is specified, the system selects the first executor in the chain that supports parallel execution capabilities.

3. **Error Handling**: If none of the available executors in the chain support parallel execution, the system raises a runtime error condition to prevent execution failures.

### Executor Compatibility

The executor selection mechanism ensures that parallel execution chains maintain consistency and performance. Only executors capable of handling concurrent operations are considered for parallel execution scenarios. This prevents runtime errors and ensures predictable behavior across different execution contexts.