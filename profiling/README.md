# Profiling Event Pipeline

This tool provides comprehensive performance profiling for different types of event pipelines. It uses cProfile to generate detailed performance statistics and supports web-based visualization through snakeviz.

## Installation

First, install the required dependencies:

\`\`\`bash
pip install snakeviz # For web visualization
\`\`\`

## Available Pipeline Types

The profiling tool supports the following pipeline types:

- **Linear** (\`-t linear\`): Sequential execution of events
- **Linear with Previous Result** (\`-t linear_pr\`): Events that can access previous results
- **Decision Tree** (\`-t decision_tree\`): Conditional branching based on event outcomes
- **Parallel** (\`-t parallel\`): Concurrent execution of events
- **Batch** (\`-t batch\`): Processing multiple items in batches

## Command Line Flags

| Flag                         | Description                 | Default    | Example         |
| ---------------------------- | --------------------------- | ---------- | --------------- |
| \`-t, --type\`               | Pipeline type to profile    | \`linear\` | \`-t parallel\` |
| \`-w, --run_in_web_browser\` | Open results in web browser | \`False\`  | \`-w True\`     |

## Usage Examples

### Basic Linear Pipeline

\`\`\`bash
python3 profiling/profiler.py -t linear
\`\`\`

### Parallel Pipeline with Web Visualization

\`\`\`bash
python3 profiling/profiler.py -t parallel -w True
\`\`\`

### Batch Processing

\`\`\`bash
python3 profiling/profiler.py -t batch
\`\`\`

### Decision Tree Pipeline

\`\`\`bash
python3 profiling/profiler.py -t decision_tree
\`\`\`

### Linear Pipeline with Previous Results

\`\`\`bash
python3 profiling/profiler.py -t linear_pr
\`\`\`

## Web Visualization

When using the \`-w True\` flag, the tool will automatically open snakeviz in your web browser to visualize the profiling results. This provides an interactive flame graph showing where time is spent in your pipeline.

## Troubleshooting

### Snakeviz Not Found

If you get an error about snakeviz not being found, install it:
\`\`\`bash
pip install snakeviz
\`\`\`

