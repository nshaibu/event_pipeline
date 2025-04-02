import typing


class Expression:

    def __init__(self, operator: str):
        self.op = operator


class BinOp(Expression):
    def __init__(self, op, left_node, right_node):
        super().__init__(op)
        self.left = left_node
        self.right = right_node

    def __repr__(self):
        return f"BinOp({self.op}, {self.left}, {self.right})"


class ConditionalGroup(Expression):
    def __init__(self, expr0: Expression, expr1: Expression):
        super().__init__("EXPRESSION-GROUP")
        self._descriptors: typing.Dict[int, BinOp] = {}

        self.set_value(expr0)
        self.set_value(expr1)

    def set_value(self, value: typing.Union[BinOp, "Expression"]):
        if value:
            if isinstance(value, BinOp):
                self._descriptors[value.left.value] = value
            elif isinstance(value, ConditionalGroup):
                for bin_op in value.get_bin_ops():
                    self._descriptors[bin_op.left.value] = bin_op

    @property
    def descriptor_dict(self):
        return self._descriptors

    def get_bin_ops(self) -> typing.List[BinOp]:
        return list(self._descriptors.values())

    def get_extra_descriptors(self) -> typing.List[BinOp]:
        return [desc for desc in self.get_bin_ops() if desc.left.value not in [1, 0]]

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
    def __init__(self, value):
        self.value = value

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
