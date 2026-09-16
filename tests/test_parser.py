# tests/test_parser.py
#
# Parses the real example and prints a summary of the AST, then checks
# two things by hand:
#   1. precedence: 2 + 3 * 4 parses as PLUS(2, MUL(3, 4)), not MUL(PLUS(2,3), 4)
#   2. a missing semicolon raises ParseError with line/col
#
# Run from the project root:  python tests/test_parser.py

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow.lexer import tokenize
from agentflow.parser import parse, describe, reduce_production
from agentflow.errors import ParseError
from agentflow.ast_nodes import BinaryExprNode, NumberLiteralNode


def main():
    example_path = os.path.join(
        os.path.dirname(__file__), "..", "examples", "order_processor.aflow"
    )
    with open(example_path, "r", encoding="utf-8") as f:
        source = f.read()

    tokens = tokenize(source)
    program = parse(tokens)
    print("Parsed OK. AST:")
    print()
    describe(program)

    # ---- precedence check ----
    print()
    print("--- precedence check: 2 + 3 * 4 ---")
    src = "workflow W { state S entry { x = 2 + 3 * 4; } }"
    prog = parse(tokenize(src))
    actions = prog.decls[0].actions
    expr = actions[0].expr
    assert isinstance(expr, BinaryExprNode) and expr.op == "PLUS", (
        "top-level operator should be PLUS"
    )
    assert isinstance(expr.right, BinaryExprNode) and expr.right.op == "MUL", (
        "right child should be MUL"
    )
    assert isinstance(expr.left, NumberLiteralNode) and expr.left.value == 2
    assert expr.right.left.value == 3 and expr.right.right.value == 4
    print("PASS: 2 + 3 * 4 parses as PLUS(2, MUL(3, 4))")

    # ---- missing semicolon check ----
    print()
    print("--- syntax error test: missing semicolon ---")
    bad = "workflow W { tool T() -> bool state S entry; }"
    try:
        parse(tokenize(bad))
        print("ERROR: expected ParseError, got none")
    except ParseError as e:
        print("ParseError caught:", e)


if __name__ == "__main__":
    main()
