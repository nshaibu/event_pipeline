import ast
import typing


class BinOp(object):
    def __init__(self, op, left_node, right_node):
        self.op = op
        self.left = left_node
        self.right = right_node


class ConditionalBinOP(object):
    def __init__(self, parent, left_node, right_node):
        self.parent = parent
        self.op = "CONDITIONAL"
        self.left = left_node
        self.right = right_node


class TaskName(object):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f"Task: {self.value}"


class Descriptor(object):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f"Descriptor: {self.value}"


def df_traverse_post_order(
    node: typing.Union[BinOp, ConditionalBinOP, TaskName, Descriptor]
):
    if node:
        if isinstance(node, (BinOp, ConditionalBinOP)):
            yield from df_traverse_post_order(node.right)
            yield from df_traverse_post_order(node.left)

        yield node
