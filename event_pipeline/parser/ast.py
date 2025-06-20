import ast
import typing
from pydantic_mini.typing import NoneType


class Expression:

    def __init__(self, operator: str):
        self.op = operator


class GroupExpression:

    def __init__(self):
        self.op = "EXPRESSION-GROUP"

    def set_value(self, value: typing.Any, initial_value: typing.Any):
        raise NotImplementedError


class AssignmentExpression(Expression):

    def __init__(self, variable: typing.Any, value: typing.Any):
        super().__init__("ASSIGNMENT")
        self.variable = variable
        self.value = value
        self.data_type: typing.Type = self.determine_value_type(self.value)

    def __str__(self):
        return f"{self.variable} = {self.value} ({self.data_type})"

    def __repr__(self):
        return f"{self.__class__.__name__}({self.variable} = {self.value} ({self.data_type}))"

    @staticmethod
    def determine_value_type(value: typing.Any) -> type:
        if value is None:
            return NoneType
        elif isinstance(value, int):
            return int
        elif isinstance(value, float):
            return float
        elif isinstance(value, str):
            try:
                value = ast.literal_eval(value)
                return type(value)
            except (ValueError, TypeError):
                return str


class AssignmentExpressionGroup(GroupExpression):

    def __init__(
        self, expr0: typing.Optional[Expression], expr1: typing.Optional[Expression]
    ):
        super().__init__()
        self._assignment_groups: typing.List[AssignmentExpression] = []

        self.set_value(expr0)
        self.set_value(expr1)

    def set_value(
        self,
        value: typing.Any,
    ):
        if value is None:
            return
        if isinstance(value, AssignmentExpression):
            self._assignment_groups.append(value)
        elif isinstance(value, AssignmentExpressionGroup):
            for expr in value.assignment_groups():
                self._assignment_groups.append(expr)

    def assignment_groups(self) -> typing.List[AssignmentExpression]:
        return self._assignment_groups


class BinOp(Expression):
    def __init__(self, op, left_node, right_node):
        super().__init__(op)
        self.left = left_node
        self.right = right_node

    def __repr__(self):
        return f"BinOp({self.op}, {self.left}, {self.right})"


class ConditionalGroup(GroupExpression):
    def __init__(self, expr0: Expression, expr1: Expression):
        super().__init__()
        self._descriptors: typing.Dict[int, BinOp] = {}

        self.set_value(expr0, expr0)
        self.set_value(expr1, expr1)

    def set_value(
        self,
        value: typing.Union[BinOp, "Expression"],
        initial_value: typing.Union[BinOp, "Expression"],
    ):
        if value:
            if isinstance(value, BinOp):
                self.set_value(value.left, initial_value)
            elif isinstance(value, ConditionalGroup):
                for bin_op in value.get_bin_ops():
                    self.set_value(bin_op.left, bin_op)
            elif isinstance(value, Descriptor):
                self._descriptors[value.value] = initial_value

    @property
    def descriptor_dict(self):
        return self._descriptors

    def get_bin_ops(self) -> typing.List[BinOp]:
        return list(self._descriptors.values())

    def get_extra_descriptors(self) -> typing.List[BinOp]:
        descriptors = []
        for key, value in self._descriptors.items():
            if key not in [1, 0]:
                descriptors.append(value)
        return descriptors

    def __repr__(self):
        return f"ConditionalGroup({self.get_bin_ops()})"


class ConditionalBinOP(Expression):
    def __init__(self, parent, expr_group: ConditionalGroup):
        super().__init__("CONDITIONAL")
        self.parent = parent
        self.expr_group = expr_group

    @property
    def descriptors_dict(self) -> typing.Dict[int, BinOp]:
        if self.expr_group:
            return self.expr_group.descriptor_dict
        return {}

    @property
    def left(self):
        return self.descriptors_dict.get(0)

    @property
    def right(self):
        return self.descriptors_dict.get(1)

    def extra_descriptors(self) -> typing.List[BinOp]:
        if self.expr_group:
            return self.expr_group.get_extra_descriptors()
        return []

    def __repr__(self):
        return (
            f"ConditionalBinOP({self.parent}, "
            f"{self.left}, {self.right}, "
            f"{self.extra_descriptors()})"
        )


class TaskName(object):
    def __init__(self, value: str, assign_group: AssignmentExpressionGroup = None):
        self.value = value
        self.options = assign_group

    def __repr__(self):
        return f"Task({self.value})"


class Descriptor(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return f"Descriptor({self.value})"


def df_traverse_post_order(
    node: typing.Union[BinOp, ConditionalBinOP, TaskName, Descriptor],
):
    if node:
        if isinstance(node, (BinOp, ConditionalBinOP)):
            yield from df_traverse_post_order(node.right)
            yield from df_traverse_post_order(node.left)

        yield node
