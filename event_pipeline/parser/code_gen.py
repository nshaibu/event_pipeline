import typing
import logging
from .visitor import ASTVisitorInterface
from .protocols import TaskProtocol, TaskGroupingProtocol
from . import ast
from .operator import PipeType

Options = object()

logger = logging.getLogger(__name__)


class ExecutableASTGenerator(ASTVisitorInterface):

    task_template: TaskProtocol

    def __init__(
        self,
        task_template: typing.Type[TaskProtocol],
        grouping_template: typing.Type[TaskGroupingProtocol],
    ):
        self.task_template = task_template
        self._generated_task_chain: typing.Optional[TaskProtocol] = None
        self._current_task: typing.Optional[TaskProtocol] = None

    def _visit_node(self, node: ast.ASTNode):
        """Generic node visitor dispatcher"""
        if isinstance(node, ast.ProgramNode):
            return self.visit_program(node)
        elif isinstance(node, ast.BinOpNode):
            return self.visit_binop(node)
        elif isinstance(node, ast.DescriptorNode):
            return self.visit_descriptor(node)
        elif isinstance(node, ast.TaskNode):
            return self.visit_task(node)
        elif isinstance(node, ast.ExpressionGroupingNode):
            return self.visit_expression_grouping(node)
        elif isinstance(node, ast.ConditionalNode):
            return self.visit_conditional(node)
        elif isinstance(node, ast.AssignmentNode):
            return self.visit_assignment(node)
        elif isinstance(node, ast.BlockNode):
            return self.visit_block(node)
        elif isinstance(node, ast.LiteralNode):
            return self.visit_literal(node)
        else:
            raise ValueError(f"Unknown node type: {type(node)}")

    def visit_program(self, node: ast.ProgramNode):
        chain = node.chain
        if chain is None:
            return
        self._generated_task_chain = None
        self._current_task = None
        self._visit_node(chain)

    def visit_binop(self, node: ast.BinOpNode):
        pass

    def visit_descriptor(self, node: ast.DescriptorNode):
        return int(node.value)

    def visit_task(self, node: ast.TaskNode):
        instance = self.task_template(event=node.task)
        if node.options:
            instance.options = Options.from_assignment_expression_group(node.options)
        return instance

    def visit_block(self, node: ast.BlockNode):
        if node.type == ast.BlockType.ASSIGNMENT:
            return self.visit_assignment_block(node)
        elif node.type == ast.BlockType.CONDITIONAL:
            return self.visit_conditional(node)
        elif node.type == ast.BlockType.GROUP:
            return self.visit_group_block(node)
        else:
            raise ValueError(f"Unknown block type: {type(node)}")

    def visit_group_block(self, node: ast.BlockNode):
        raise NotImplementedError("Not Supported yet")

    def visit_literal(self, node: ast.LiteralNode):
        return node.value

    def visit_assignment(self, node: ast.AssignmentNode):
        return {node.target: node.value}

    def visit_assignment_block(
        self, node: ast.BlockNode
    ) -> typing.Dict[str, typing.Any]:
        assign = {}
        for statement in node.statements:
            assign.update(statement)
        return assign

    def visit_expression_grouping(self, node: ast.ExpressionGroupingNode):
        pass

    def visit_conditional(self, node: ast.ConditionalNode):
        parent = self.visit_task(node.task)

        for node in node.branches.statements:
            instance = self._visit_node(node)
            if instance:
                instance = instance.get_root()
                instance.parent_node = parent
                if instance.descriptor == 0:
                    parent.on_failure_event = instance
                    parent.on_failure_pipe = PipeType.get_pipe_type_enum(
                        instance.descriptor_pipe
                    )
                elif instance.descriptor == 1:
                    parent.on_success_event = instance
                    parent.on_success_pipe = PipeType.get_pipe_type_enum(
                        instance.descriptor_pipe
                    )
                else:
                    is_added = parent.extra_config.add_descriptor(
                        instance.descriptor,
                        PipeType.get_pipe_type_enum(instance.descriptor_pipe),
                        instance,
                    )
                    if not is_added:
                        logger.warning(
                            f"Failed to add descriptor {instance.descriptor} for event {node}"
                        )

        return parent

    def generate(self) -> TaskProtocol:
        pass
