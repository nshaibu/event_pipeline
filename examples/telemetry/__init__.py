"""
Example implementations demonstrating the telemetry features of event-pipeline.

This package contains examples showing how to:
- Enable telemetry collection
- Monitor event execution
- Track performance metrics
- Handle remote execution telemetry
"""

from .events import DataProcessingEvent, run_example

__all__ = ["DataProcessingEvent", "run_example"]
