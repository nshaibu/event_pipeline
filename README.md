<div style="display: flex; align-items: center;">
  <img alt="pipeline" height="60" src="img/pipeline.svg" width="60" style="margin-right: 10px; vertical-align: middle;"/>
  <h1 style="margin: 0; vertical-align: middle;">Event Pipeline</h1>
</div>


[![Build Status](https://github.com/nshaibu/event_pipeline/actions/workflows/python_package.yml/badge.svg)](https://github.com/nshaibu/event_pipeline/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Status](https://img.shields.io/pypi/status/event-pipeline.svg)](https://pypi.python.org/pypi/event-pipeline)
[![Latest](https://img.shields.io/pypi/v/event-pipeline.svg)](https://pypi.python.org/pypi/event-pipeline)
[![PyV](https://img.shields.io/pypi/pyversions/event-pipeline.svg)](https://pypi.python.org/pypi/event-pipeline)

[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com)

# Table of Contents
1. [Introduction](#Introduction)
   1. [Installation](#Installation)
   2. [Requirements](#Requirements)
2. [Usage](#Usage)
    1. [Pipeline](#pipeline)
       1. [Defining Pipelines](#defining-pipeline)
       2. [Defining input data field](#defining-input-data-field)
       3. [Defining Pipeline Structure Using Pointy language](#defining-pipeline-structure)
       4. [Pointy Language](#pointy-language)
       5. [Executing Pipeline](#executing-pipeline)
       6. [Batch Processing (WIP)](#)
       7. [Scheduling (WIP)](#)
          1. [Periodic Scheduling (CRON) (WIP)](#)
    2. [Event](#defining-events)
       1. [Defining Events](#define-the-event-class)
       2. [Specify the Executor for your Event](#specify-the-executor-for-the-event)
       3. [Function-Based Events (WIP)](#function-based-events)
       4. [Event Result Evaluation](#event-result-evaluation)
       5. [Specifying Event Retry Policy](#specifying-a-retry-policy-for-event)
          1. [RetryPolicy Class](#retrypolicy-class)
          2. [Configuring The Retry Policy](#configuring-the-retrypolicy)
          3. [Assigning Retry Policy](#assigning-the-retry-policy-to-an-event)
          4. [How the retry Policy Works](#how-the-retry-policy-works)
   3. [Signals](#signals)
      1. [Soft Signal framework](#soft-signaling-framework)
         1. [Default Signals](#default-signals)
         2. [Connecting Signal Listeners](#connecting-listeners-to-signals)

# Introduction
This library provides an easy-to-use framework for defining and managing events and pipelines. 
It allows you to create events, process data through a series of tasks, and manage complex workflows
with minimal overhead. The library is designed to be extensible and flexible, enabling developers to 
easily integrate it into their projects.

## Features
- Define and manage events and pipelines in Python.
- Support for conditional task execution.
- Easy integration of custom event processing logic.
- Supports remote task execution and distributed processing.
- Seamless handling of task dependencies and event execution flow.

## Installation
To install the library, simply use pip:

```bash
pip install event-pipeline
```

# Requirements
- Python>=3.8
- ply==3.11 
- treelib==1.7.0 
- graphviz==0.20.3 (Optional)

# Usage

# Pipeline

## Defining Pipeline

To define a pipeline, import the Pipeline class from the event_pipeline module and create a new class that
inherits from it. This custom class will define the behavior and structure of your pipeline.

```python
from event_pipeline import Pipeline

class MyPipeline(Pipeline):
    # Your input data fields will go here
    pass

```

## Defining Input Data Field
Import the `InputDataField` or another class from the fields module. 

The InputDataField class is used to define the input fields for your pipeline. These fields are assigned as attributes 
within your pipeline class and represent the data that will flow through the pipeline.
Events within the pipeline can request for the values of the Input fields by including the name 
of the field in their `process` method arguments.

```python
from event_pipeline import Pipeline
from event_pipeline.fields import InputDataField

class MyPipeline(Pipeline):
    # Define input fields as attributes
    input_field = InputDataField(data_type=str, required=True)  # Define an input field

```

## Defining Pipeline Structure
The next step is to define the structure and flow of your pipeline using the pointy language. 
The pointy file provides a structured format to describe how the pipeline should execute, 
including the order of tasks, conditions, and dependencies.

```pty
Fetch->Process->Execute->SaveToDB->Return
```

The pointy file `.pty` describes the flow of tasks and their dependencies, allowing you to build dynamic 
and conditional pipelines based on the results of previous executed event.

By default, if the name of your pointy file matches the name of your pipeline class, the library 
will automatically load the pointy file for you. For example, if your class is named MyPipeline, 
it will automatically look for a file named `MyPipeline.pty`.

If you want to use a pointy file with a different name, you can define a Meta subclass inside 
your pipeline class. 

This subclass should specify the file or pointy property:

- `pointy`: The string of the pointy script.
- `file`: The full path to your pointy file.

Example of how to define the Meta subclass:
```python
class MyPipeline(Pipeline):
    class Meta:
        pointy = "A->B->C"  # Pointy script
        # OR
        file = "/path/to/your/custom_pipeline.pty"  # Full path to your pointy file

# You can also define the options as dictionary

class MyPipeline(Pipeline):
    meta = {
        "pointy": "A->B->C",
        # OR
        "file": "/path/to/your/custom_pipeline.pty"
    }
```

## Pointy Language

- Single event: 

```pty
A    # single event
```

- Directional operation

```pty
A -> B   # Execute A then move to B
```

- Parallel operation

```pty
A || B  # Execute A and B in parallel

A || B |-> C # Execute A and B in parallel then pipe their results to C
```

- Broadcasting with one sink node
```pty
A |-> B || C || D |-> E
```

- Two events with result piping

```pty
A |-> B   # Piping result of execution of A to event B
```

- Multiple events with branching

```pty
A -> B (0 -> C, 1 -> D) # 0 for failure, 1 for success 
```

- Multiple events with sink

```pty
A (0 -> B, 1 -> C) -> D
```

## Example

```pty
A -> B (
    0->C (
        0 |-> T,
        1 -> Z
    ),
    1 -> E
) -> F (
    0 -> Y,
    1 -> Z
)
```
This is the graphical representation of the above pipeline

![pipeline](img/Simple.png)

To draw your pipeline:
```python
# instantiate your pipeline clas
pipeline = MyPipeline()

# draw ascii representation
pipeline.draw_ascii_graph()

# draw graphical representation # (requires graphviz, xdot)
pipeline.draw_graphviz_image(directory=...)

```
## Executing Pipeline
Execute your pipeline by making calls to the `start` method:

```python
# instantiate your pipeline class
pipeline = MyPipeline(input_field="value")

# call start
pipeline.start()
```


# Defining Events

## Define the Event Class

To define an event, you need to inherit from the EventBase class and override the process method. 
This process method defines the logic for how the event is executed.

```python
from event_pipeline import EventBase

class MyEvent(EventBase):
    def process(self, *args, **kwargs):
        # Event processing logic here
        return True, "Event processed successfully"
```

## Specify the Executor for the Event

Every event must specify an executor that defines how the event will be executed. Executors are 
responsible for managing the concurrency or parallelism when the event is being processed.

Executors implement the Executor interface from the concurrent.futures._base module in the 
Python standard library. If no executor is specified, the DefaultExecutor will be used.

```python
from concurrent.futures import ThreadPoolExecutor

class MyEvent(EventBase):
    executor = ThreadPoolExecutor  # Specify executor for the event
    
    def process(self, *args, **kwargs):
        # Event processing logic here
        return True, "Event processed successfully"

```

If you are using `ProcessPoolExecutor` or `ThreadPoolExecutor`, you can configure additional properties
to control the behavior of the executor:

- `max_workers`: Specifies the maximum number of workers (processes or threads) that can be used to 
execute the event. If not provided, the number of workers will default to the number of processors on the machine.

- `max_tasks_per_child`: Defines the maximum number of tasks a worker can complete before being replaced with a 
fresh worker. By default, workers will live as long as the executor unless this property is set.

- `thread_name_prefix`: A prefix to use for naming threads. This helps identify threads related to your event during execution.

Here’s how you can set these properties:

```python
from concurrent.futures import ThreadPoolExecutor

class MyEvent(EventBase):
    executor = ThreadPoolExecutor
    
    # Configure the executor
    max_workers = 4  # Max number of workers
    max_tasks_per_child = 10  # Max tasks per worker before replacement
    thread_name_prefix = "my_event_executor"  # Prefix for thread names
    
    def process(self, *args, **kwargs):
        # Event processing logic here
        return True, "Event processed successfully"

```
## Executor Configuration

The `ExecutorInitializerConfig` class is used to configure the initialization of an executor 
(such as ProcessPoolExecutor or ThreadPoolExecutor) that manages event processing. This class allows you 
to control several aspects of the executor’s behavior, including the number of workers, task limits, 
and thread naming conventions.

### Configuration Fields
The ExecutorInitializerConfig class contains the following configuration fields:

1. `max_workers`
    - **Type**: `int` or `EMPTY`
    - ***Description***: Specifies the maximum number of workers (processes or threads) that can be used to execute 
    the event. If this is not provided, the number of workers defaults to the number of processors available on the machine.
    - ***Usage***: Set this field to an integer value if you wish to limit the number of workers. If left as EMPTY, 
    the system will use the default number of workers based on the machine’s processor count.

2. `max_tasks_per_child`
   - ***Type***: `int` or `EMPTY`
   - ***Description***: Defines the maximum number of tasks a worker can complete before being replaced by a new worker. 
   This can be useful for limiting the lifetime of a worker, especially for long-running tasks, to avoid memory buildup 
   or potential issues with task state.
   - ***Usage***: Set this field to an integer to limit the number of tasks per worker. If set to EMPTY, workers will 
   live for as long as the executor runs.

3. `thread_name_prefix`
    - ***Type***: `str` or `EMPTY`
    - ***Description***: A string to use as a prefix when naming threads. This helps identify threads related to event 
    processing during execution.
    - ***Usage***: Set this field to a string to provide a custom thread naming convention. If left as EMPTY, 
    threads will not have a prefix.

Here’s an example of how to use the ExecutorInitializerConfig class to configure an executor for event processing:

```python
from some_module import ExecutorInitializerConfig

# Configuring an executor with a specific number of workers, max tasks per worker, and thread name prefix
config = ExecutorInitializerConfig(
    max_workers=4,
    max_tasks_per_child=50,
    thread_name_prefix="event_executor_"
)

# Pass the config to the executor initializer
executor_initializer = ExecutorInitializer(config)
executor_initializer.initialize_executor()
```

In this example:

The executor will allow 4 workers (processes or threads, depending on the executor type).
Each worker will process a maximum of 50 tasks before being replaced.
The thread names will begin with the prefix event_executor_, making it easier to identify threads related 
to event processing.

## Default Behavior
If no fields are specified or left as EMPTY, the executor will use the following default behavior:

max_workers: The number of workers will default to the number of processors on the machine.
max_tasks_per_child: Workers will continue processing tasks indefinitely, with no limit.
thread_name_prefix: Threads will not have a custom prefix.
For example, the following code creates an executor with default behavior:

```python
config = ExecutorInitializerConfig()  # Default configuration
```


## Function-Based Events
In addition to defining events using classes, you can also define events as functions. 
This is achieved by using the event decorator from the decorators module.

The decorator allows you to configure the executor, just like in class-based events, 
providing flexibility for execution.

```python
from event_pipeline.decorators import event

# Define a function-based event using the @event decorator
@event()
def my_event(*args, **kwargs):
    # Event processing logic here
    return True, "Event processed successfully"
```

The event decorator allows you to define an event as a simple function. You can also configure the 
executor for the event's execution using parameters like max_workers, max_tasks_per_child, and thread_name_prefix.

```python
from event_pipeline.decorators import event
from concurrent.futures import ThreadPoolExecutor

# Define a function-based event using the @event decorator
@event(
    executor=ThreadPoolExecutor,               # Define the executor to use for event execution
    max_workers=4,                             # Specify max workers for ThreadPoolExecutor
    max_tasks_per_child=10,                    # Limit tasks per worker
    thread_name_prefix="my_event_executor",    # Prefix for thread names
    stop_on_exception=True                     # Flag to stop execution if an exception occurs
)
def my_event(*args, **kwargs):
    # Event processing logic here
    return True, "Event processed successfully"
```
The `@event` decorator registers the function as an event in the pipeline and configures the executor for the event execution.

## Event Result Evaluation
The `EventExecutionEvaluationState` class defines the criteria for evaluating the success or failure of an event 
based on the outcomes of its tasks. The states available are:

- `SUCCESS_ON_ALL_EVENTS_SUCCESS`: The event is considered successful only if all the tasks within the event succeeded. 
If any task fails, the evaluation is marked as a failure. This is the `default` state.

- `FAILURE_FOR_PARTIAL_ERROR`: The event is considered a failure if any of the tasks fail. Even if some tasks succeed, 
a failure in any one task results in the event being considered a failure.

- `SUCCESS_FOR_PARTIAL_SUCCESS`: This state treats the event as successful if at least one task succeeds. Even if 
other tasks fail, the event will be considered successful as long as one succeeds.

- `FAILURE_FOR_ALL_EVENTS_FAILURE`: The event is considered a failure only if all tasks fail. If any task succeeds, 
the event is marked as successful.

Each state can be used to configure how an event's success or failure is determined, allowing for flexibility 
in managing workflows.

### Example Usage
Here's how you can set the execution evaluation state in your event class:

```python
from event_pipeline import EventBase, EventExecutionEvaluationState

class MyEvent(EventBase):
    execution_evaluation_state = EventExecutionEvaluationState.SUCCESS_ON_ALL_EVENTS_SUCCESS
    
    def process(self, *args, **kwargs):
        return True, "obrafour"

```

## Specifying a Retry Policy for Event
In some scenarios, you may want to define a retry policy for handling events that may fail intermittently. 
The retry policy allows you to configure things like the maximum number of retry attempts, the backoff strategy, 
and which exceptions should trigger a retry.

The retry policy can be specified by importing the RetryPolicy class and configuring the respective fields. 
You can then assign this policy to your event class, ensuring that failed events will be retried based on 
the configured settings.

### RetryPolicy Class
The RetryPolicy class allows you to define a policy with the following parameters:

```python
@dataclass
class RetryPolicy(object):
    max_attempts: int   # Maximum retry attempts
    backoff_factor: float  # Backoff time between retries
    max_backoff: float # Maximum allowed backoff time
    retry_on_exceptions: typing.List[typing.Type[Exception]]  # List of exceptions that will trigger a retry
```

### Configuring the RetryPolicy
To configure a retry policy, you can create an instance of RetryPolicy and set its fields based on your desired 
settings. The retry policy can also be defined as a dictionary.

For example:

```python
from event_pipeline.base import RetryPolicy

# Define a custom retry policy
retry_policy = RetryPolicy(
    max_attempts=5,  # Maximum number of retries
    backoff_factor=0.1,  # 10% backoff factor
    max_backoff=5.0,  # Max backoff of 5 seconds
    retry_on_exceptions=[ConnectionError, TimeoutError]  # Retry on specific exceptions
)

# Or define the retry policy as a dictionary
retry_policy = {
    "max_attempts": 5,
    "backoff_factor": 0.1,
    "max_backoff": 5.0,
    "retry_on_exceptions": [ConnectionError, TimeoutError]
}
```
In this example:
- `max_attempts` specifies the maximum number of times the event will be retried before it gives up.
- `backoff_factor` defines how long the system will wait between retry attempts, increasing with each retry.
- `max_backoff specifies` the maximum time to wait between retries, ensuring it doesn't grow indefinitely.
- `retry_on_exceptions` is a list of exception types that should trigger a retry. If an event fails due to 
one of these exceptions, it will be retried.

### Assigning the Retry Policy to an Event

Once you have defined the RetryPolicy, you can assign it to your event class for processing. 
The policy can be passed as a dictionary containing the retry configuration.

Here’s how you can assign the retry policy to your event class:

```python
import typing
from event_pipeline import EventBase


class MyEvent(EventBase):
    
    # assign instance of your RetryPolicy or RetryPolicy dictionary
    retry_policy = retry_policy 

    def process(self, *args, **kwargs) -> typing.Tuple[bool, typing.Any]:
        pass

```

In this example, the `retry_policy` class variable is assign the retry configuration.

# How the Retry Policy Works
When an event is processed, if it fails due to an exception in the retry_on_exceptions list, the retry logic kicks in:

- The system will retry the event based on the `max_attempts`.
- After each retry attempt, the system waits for a time interval determined by the `backoff_factor` 
and will not exceed the `max_backoff`.
- If the maximum retry attempts are exceeded, the event will be marked as failed.

- This retry mechanism ensures that intermittent failures do not cause a complete halt in processing and 
allows for better fault tolerance in your system.

# Signals

## Soft Signaling Framework

The Signaling Framework is a core component of the Event-Pipeline library, enabling you to connect custom behaviors 
to specific points in the lifecycle of a pipeline and its events. The framework utilizes the `SoftSignal` class, 
which allows for easy connection of listeners to signals. This enables the implementation of custom logic that 
can be executed at critical moments in your pipeline's operation.

### Default Signals

The following default signals are provided for various stages of the pipeline:

#### Initialization Signals

- **`pipeline_pre_init`**:
  - **Description**: This signal is emitted before the pipeline is initialized. It allows you to execute logic right at the start of the initialization process.
  - **Arguments**:
    - `cls`: The class of the pipeline being initialized.
    - `args`: Positional arguments passed during initialization.
    - `kwargs`: Keyword arguments passed during initialization.

- **`pipeline_post_init`**:
  - **Description**: This signal is emitted after the pipeline has been successfully initialized. You can use this to perform actions that depend on the pipeline being ready.
  - **Arguments**:
    - `pipeline`: The instance of the initialized pipeline.

#### Shutdown Signals

- **`pipeline_shutdown`**:
  - **Description**: Emitted when the pipeline is shutting down. This is an opportunity to clean up resources or save state.
  - **Arguments**: None

- **`pipeline_stop`**:
  - **Description**: Triggered when the pipeline is stopped. This can be useful for halting ongoing operations or notifications.
  - **Arguments**: None

#### Execution Signals

- **`pipeline_execution_start`**:
  - **Description**: This signal is emitted when the execution of the pipeline begins. It's useful for logging or starting monitoring.
  - **Arguments**:
    - `pipeline`: The instance of the pipeline that is starting execution.

- **`pipeline_execution_end`**:
  - **Description**: Triggered when the execution of the pipeline has completed. You can use this for final logging or cleanup.
  - **Arguments**:
    - `execution_context`: Context information about the execution, such as status and results.

#### Event Execution Signals

- **`event_execution_init`**:
  - **Description**: Emitted when an event execution is initialized. This can be used to set up necessary preconditions for the event processing.
  - **Arguments**:
    - `event`: The event being processed.
    - `execution_context`: The context in which the event is executed.
    - `executor`: The executor responsible for handling the event.
    - `call_kwargs`: Additional keyword arguments for the event execution.

- **`event_execution_start`**:
  - **Description**: This signal is emitted when the execution of a specific event starts. It’s useful for tracking the start of event processing.
  - **Arguments**:
    - `event`: The event that is starting.
    - `execution_context`: The context in which the event is being executed.

- **`event_execution_end`**:
  - **Description**: Triggered when the execution of an event ends. This is useful for post-processing or finalizing the event's outcomes.
  - **Arguments**:
    - `event`: The event that has finished execution.
    - `execution_context`: The context in which the event was executed.
    - `future`: A future object representing the result of the event execution.

- **`event_execution_retry`**:
  - **Description**: Emitted when an event execution is retried. This is useful for tracking retries and implementing custom backoff strategies.
  - **Arguments**:
    - `event`: The event being retried.
    - `execution_context`: The context for the retry execution.
    - `task_id`: The identifier for the specific task being retried.
    - `backoff`: The backoff strategy or duration.
    - `retry_count`: The current count of retries that have been attempted.
    - `max_attempts`: The maximum number of allowed attempts.

- **`event_execution_retry_done`**:
  - **Description**: Triggered when a retry of an event execution is completed. This can be useful for logging or updating the state after retries.
  - **Arguments**:
    - `event`: The event that has completed its retry process.
    - `execution_context`: The context in which the event was executed.
    - `task_id`: The identifier for the task that was retried.
    - `max_attempts`: The maximum number of attempts that were allowed for the task.

### Connecting Listeners to Signals

To leverage the signaling framework, you can connect listeners to these signals. Listeners are functions that will be 
called when a specific signal is emitted. Here's how to connect a listener:

```python
from event_pipeline.signal.signals import pipeline_execution_start
from event_pipeline import Pipeline

def my_listener(pipeline):
    print(f"Execution starting for pipeline: {pipeline}")

# Connect the listener to the signal
pipeline_execution_start.connect(my_listener, sender=Pipeline)
```
### Or
```python
from event_pipeline.decorators import listener
from event_pipeline.signal.signals import pipeline_pre_init
from event_pipeline import Pipeline

@listener(pipeline_pre_init, sender=Pipeline)
def my_lister(sender, signal, *args, **kwargs):
    print("Executing pipeline")

```


# Contributing
We welcome contributions! If you have any improvements, fixes, or new features, 
feel free to fork the repository and create a pull request.

# Reporting Issues
If you find a bug or have suggestions for improvements, please open an issue in the repository. 
Provide as much detail as possible, including steps to reproduce the issue, expected vs. actual behavior, and any relevant logs or error messages.

# License
This project is licensed under the GNU GPL-3.0 License - see the LICENSE file for details.