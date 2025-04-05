__all__ = ["pointy_parser"]

from . import lexer
from ply.yacc import yacc, YaccError

from .ast import BinOp, Descriptor, TaskName, ConditionalBinOP, ConditionalGroup

pointy_lexer = lexer.PointyLexer()
tokens = pointy_lexer.tokens

precedence = (("left", "RETRY", "POINTER", "PPOINTER", "PARALLEL"),)


def p_expression(p):
    """
    expression :  expression POINTER expression
                | expression PPOINTER expression
                | expression PARALLEL expression
                | descriptor POINTER expression
                | descriptor PPOINTER expression
                | factor RETRY task
                | task RETRY factor
    """
    p[0] = BinOp(p[2], p[1], p[3])


def p_expression_term(p):
    """
    expression : term
    """
    p[0] = p[1]


def p_task(p):
    """
    term : task
    """
    p[0] = p[1]


def p_descriptor(p):
    """
    descriptor : NUMBER
    """
    # p[0] = ("DESCRIPTOR", p[1])
    if 0 <= p[1] < 10:
        p[0] = Descriptor(p[1])
    else:
        line = p.lineno(1) if hasattr(p, "lineno") else "unknown line"
        column = p.lexpos(1) if hasattr(p, "lexpos") else "unknown column"
        raise YaccError(
            f"Descriptors cannot be either greater 9 or less than 0. "
            f"Line: {line}, Column: {column}, Offending token: {p[1]}"
        )


def p_factor(p):
    """
    factor : NUMBER
    """
    if p[1] < 2:
        line = p.lineno(1) if hasattr(p, "lineno") else "unknown line"
        column = p.lexpos(1) if hasattr(p, "lexpos") else "unknown column"
        raise YaccError(
            f"Task cannot be retried less than 2 times. "
            f"Line: {line}, Column: {column}, Offending Token: {p[1]}"
        )

    p[0] = p[1]


def p_task_taskname(p):
    """
    task : TASKNAME
    """
    # p[0] = ("TASKNAME", p[1])
    p[0] = TaskName(p[1])


def p_task_group(p):
    """
    task_group : expression SEPERATOR expression
                | task_group SEPERATOR expression
    """
    # p[0] = ("expr_group", p[1], p[3])
    p[0] = ConditionalGroup(p[1], p[3])


def p_task_conditional_statement(p):
    """
    task :  task LPAREN task_group RPAREN
    """
    # p[0] = ("GROUP", p[1], p[3])
    p[0] = ConditionalBinOP(p[1], p[3])


def p_error(p):
    if p is None:
        raise SyntaxError("Syntax error at the end of the input!")
    else:
        line = p.lineno if hasattr(p, "lineno") else "unknown line"
        column = p.lexpos if hasattr(p, "lexpos") else "unknown column"
        text = p.value if hasattr(p, "value") else "unknown token"

        error_message = f"Syntax error in input at line {line}, Column {column}, Offending token: {text}"

        if hasattr(p, "lexer") and p.lexer:
            _lexer = p.lexer
            _lexer.input(_lexer.lexdata)  # Reset lexer input to parse again
            for _ in range(line - 1):
                next(_lexer)
            error_context = next(_lexer)
            error_message += f"\nError occurred near: {error_context.value.strip()}"

        raise SyntaxError(error_message)


parser = yacc()


def pointy_parser(code: str):
    try:
        return parser.parse(code, lexer=pointy_lexer.lexer)
    except YaccError as e:
        raise SyntaxError(f"Parsing error: {str(e)}")
