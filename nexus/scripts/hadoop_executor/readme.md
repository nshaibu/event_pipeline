# Hadoop Setup
- Ensure the mapper/reducer scripts are available on the Hadoop nodes
- These would be deployed as part of the application setup

# Example 
```python
from hadoop_executor import HadoopExecutor
from my_events import MyHadoopTask  # Extends EventBase

# Create executor
executor = HadoopExecutor(
    host="hadoop-master.example.com",
    port=8020,
    username="hadoop_user",
    password="secret",
    poll_interval=2.0
)

# Submit tasks
future = executor.submit(
    MyHadoopTask(), 
    input_path="/data/input.csv", 
    output_path="/data/results/"
)

# Get results
try:
    result = future.result()  # Blocks until the job completes
    print(f"Job completed with result: {result}")
except Exception as e:
    print(f"Job failed: {e}")

# Or use as context manager
with HadoopExecutor() as executor:
    futures = [
        executor.submit(MyHadoopTask(), data=item)
        for item in data_items
    ]
    for future in futures:
        print(future.result())
```