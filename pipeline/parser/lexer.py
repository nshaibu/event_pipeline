from ply.lex import lex


class PointyLexer(object):
    tokens = (
        "SEPERATOR",
        "POINTER",
        "PPOINTER",
        "PARALLEL",
        "TASKNAME",
        "COMMENT",
        "LPAREN",
        "RPAREN",
        "DESCRIPTOR",
    )

    t_ignore = " \t"
    t_LPAREN = r"\("
    t_RPAREN = r"\)"
    t_TASKNAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
    t_POINTER = r"\-\>"
    t_PPOINTER = r"\|\-\>"
    t_PARALLEL = r"\|\|"
    t_SEPERATOR = r","
    t_DESCRIPTOR = r"[01]"
    t_ignore_COMMENT = r"\#.*"

    def t_newline(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    def t_error(self, t):
        print(f"Illegal character '{t.value[0]}' on line '{t.lexer.lineno}'")
        t.lexer.skip(1)

    def __init__(self, **kwargs):
        self.lexer = lex(module=self, **kwargs)
