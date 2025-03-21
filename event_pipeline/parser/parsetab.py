# parsetab.py
# This file is automatically generated. Do not edit.
# pylint: disable=W,C,R
_tabversion = "3.10"

_lr_method = "LALR"

_lr_signature = "leftRETRYPOINTERPPOINTERPARALLELCOMMENT DIRECTIVE LPAREN NUMBER PARALLEL POINTER PPOINTER RETRY RPAREN SEPERATOR TASKNAME\n    expression :  expression POINTER expression\n                | expression PPOINTER expression\n                | expression PARALLEL expression\n                | descriptor POINTER expression\n                | descriptor PPOINTER expression\n                | factor RETRY task\n                | task RETRY factor\n    \n    expression : term\n    \n    term : task\n    \n    descriptor : NUMBER\n    \n    factor : NUMBER\n    \n    task : TASKNAME\n    \n    task :  task LPAREN expression SEPERATOR expression RPAREN\n    "

_lr_action_items = {
    "NUMBER": (
        [
            0,
            8,
            9,
            10,
            11,
            12,
            14,
            15,
            25,
        ],
        [
            6,
            6,
            6,
            6,
            6,
            6,
            23,
            6,
            6,
        ],
    ),
    "TASKNAME": (
        [
            0,
            8,
            9,
            10,
            11,
            12,
            13,
            15,
            25,
        ],
        [
            7,
            7,
            7,
            7,
            7,
            7,
            7,
            7,
            7,
        ],
    ),
    "$end": (
        [
            1,
            4,
            5,
            7,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            27,
        ],
        [
            0,
            -9,
            -8,
            -12,
            -1,
            -2,
            -3,
            -4,
            -5,
            -6,
            -7,
            -11,
            -13,
        ],
    ),
    "POINTER": (
        [
            1,
            2,
            4,
            5,
            6,
            7,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            26,
            27,
        ],
        [
            8,
            11,
            -9,
            -8,
            -10,
            -12,
            -1,
            -2,
            -3,
            -4,
            -5,
            -6,
            -7,
            -11,
            8,
            8,
            -13,
        ],
    ),
    "PPOINTER": (
        [
            1,
            2,
            4,
            5,
            6,
            7,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            26,
            27,
        ],
        [
            9,
            12,
            -9,
            -8,
            -10,
            -12,
            -1,
            -2,
            -3,
            -4,
            -5,
            -6,
            -7,
            -11,
            9,
            9,
            -13,
        ],
    ),
    "PARALLEL": (
        [
            1,
            4,
            5,
            7,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            26,
            27,
        ],
        [
            10,
            -9,
            -8,
            -12,
            -1,
            -2,
            -3,
            -4,
            -5,
            -6,
            -7,
            -11,
            10,
            10,
            -13,
        ],
    ),
    "RETRY": (
        [
            3,
            4,
            6,
            7,
            27,
        ],
        [
            13,
            14,
            -11,
            -12,
            -13,
        ],
    ),
    "LPAREN": (
        [
            4,
            7,
            21,
            27,
        ],
        [
            15,
            -12,
            15,
            -13,
        ],
    ),
    "SEPERATOR": (
        [
            4,
            5,
            7,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            27,
        ],
        [
            -9,
            -8,
            -12,
            -1,
            -2,
            -3,
            -4,
            -5,
            -6,
            -7,
            -11,
            25,
            -13,
        ],
    ),
    "RPAREN": (
        [
            4,
            5,
            7,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            26,
            27,
        ],
        [
            -9,
            -8,
            -12,
            -1,
            -2,
            -3,
            -4,
            -5,
            -6,
            -7,
            -11,
            27,
            -13,
        ],
    ),
}

_lr_action = {}
for _k, _v in _lr_action_items.items():
    for _x, _y in zip(_v[0], _v[1]):
        if not _x in _lr_action:
            _lr_action[_x] = {}
        _lr_action[_x][_k] = _y
del _lr_action_items

_lr_goto_items = {
    "expression": (
        [
            0,
            8,
            9,
            10,
            11,
            12,
            15,
            25,
        ],
        [
            1,
            16,
            17,
            18,
            19,
            20,
            24,
            26,
        ],
    ),
    "descriptor": (
        [
            0,
            8,
            9,
            10,
            11,
            12,
            15,
            25,
        ],
        [
            2,
            2,
            2,
            2,
            2,
            2,
            2,
            2,
        ],
    ),
    "factor": (
        [
            0,
            8,
            9,
            10,
            11,
            12,
            14,
            15,
            25,
        ],
        [
            3,
            3,
            3,
            3,
            3,
            3,
            22,
            3,
            3,
        ],
    ),
    "task": (
        [
            0,
            8,
            9,
            10,
            11,
            12,
            13,
            15,
            25,
        ],
        [
            4,
            4,
            4,
            4,
            4,
            4,
            21,
            4,
            4,
        ],
    ),
    "term": (
        [
            0,
            8,
            9,
            10,
            11,
            12,
            15,
            25,
        ],
        [
            5,
            5,
            5,
            5,
            5,
            5,
            5,
            5,
        ],
    ),
}

_lr_goto = {}
for _k, _v in _lr_goto_items.items():
    for _x, _y in zip(_v[0], _v[1]):
        if not _x in _lr_goto:
            _lr_goto[_x] = {}
        _lr_goto[_x][_k] = _y
del _lr_goto_items
_lr_productions = [
    ("S' -> expression", "S'", 1, None, None, None),
    (
        "expression -> expression POINTER expression",
        "expression",
        3,
        "p_expression",
        "grammar.py",
        16,
    ),
    (
        "expression -> expression PPOINTER expression",
        "expression",
        3,
        "p_expression",
        "grammar.py",
        17,
    ),
    (
        "expression -> expression PARALLEL expression",
        "expression",
        3,
        "p_expression",
        "grammar.py",
        18,
    ),
    (
        "expression -> descriptor POINTER expression",
        "expression",
        3,
        "p_expression",
        "grammar.py",
        19,
    ),
    (
        "expression -> descriptor PPOINTER expression",
        "expression",
        3,
        "p_expression",
        "grammar.py",
        20,
    ),
    (
        "expression -> factor RETRY task",
        "expression",
        3,
        "p_expression",
        "grammar.py",
        21,
    ),
    (
        "expression -> task RETRY factor",
        "expression",
        3,
        "p_expression",
        "grammar.py",
        22,
    ),
    ("expression -> term", "expression", 1, "p_expression_term", "grammar.py", 29),
    ("term -> task", "term", 1, "p_task", "grammar.py", 36),
    ("descriptor -> NUMBER", "descriptor", 1, "p_descriptor", "grammar.py", 43),
    ("factor -> NUMBER", "factor", 1, "p_factor", "grammar.py", 59),
    ("task -> TASKNAME", "task", 1, "p_task_taskname", "grammar.py", 74),
    (
        "task -> task LPAREN expression SEPERATOR expression RPAREN",
        "task",
        6,
        "p_task_grouped",
        "grammar.py",
        82,
    ),
]
