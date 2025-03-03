import logging
from ply.lex import lex
from event_pipeline.utils import _extend_recursion_depth


logger = logging.getLogger(__name__)


class PointyLexer(object):
    directives = ("recursive-depth",)

    tokens = (
        "SEPERATOR",
        "POINTER",
        "PPOINTER",
        "PARALLEL",
        "RETRY",
        "TASKNAME",
        "COMMENT",
        "LPAREN",
        "RPAREN",
        "NUMBER",
        "DIRECTIVE",
    )

    t_ignore = " \t"
    t_LPAREN = r"\("
    t_RPAREN = r"\)"
    t_TASKNAME = r"[a-zA-Z_][a-zA-Z0-9_]*"
    t_POINTER = r"\-\>"
    t_PPOINTER = r"\|\-\>"
    t_RETRY = r"\*"
    t_PARALLEL = r"\|\|"
    t_SEPERATOR = r","
    t_ignore_COMMENT = r"\#.*"

    def t_NUMBER(self, t):
        r"\d+"
        t.value = int(t.value)
        return t

    def t_DIRECTIVE(self, t):
        r"\@[a-zA-Z0-9-]+:{1}[a-zA-Z0-9]+"
        value = str(t.value).lstrip("@")
        directive, value = value.split(":")
        if directive in self.directives:
            if value.isnumeric():
                if directive == "recursive-depth":
                    limit = int(value)
                    ret = _extend_recursion_depth(limit)
                    if isinstance(ret, Exception):
                        logger.warning(str(ret))
        t.lexer.skip(1)

    def t_newline(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    def t_error(self, t):
        print(f"Illegal character '{t.value[0]}' on line '{t.lexer.lineno}'")
        t.lexer.skip(1)

    def __init__(self, **kwargs):
        self.lexer = lex(module=self, **kwargs)
