from .task import PipelineTask, PipelineTaskGrouping
from event_pipeline.parser import pointy_parser
from event_pipeline.parser.code_gen import ExecutableASTGenerator


def build_pipeline_flow_from_pointy_code(code: str):
    """
    Build a pipeline flow from Pointy code.
    Args:
        code (str): The Pointy code as a string.
    Returns:
        The constructed pipeline flow.
    """
    ast = pointy_parser(code)
    code_generator = ExecutableASTGenerator(PipelineTask, PipelineTaskGrouping)
    code_generator.visit_program(ast)
    return code_generator.generate()
