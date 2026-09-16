# tests/test_lexer.py
#
# Two checks on the lexer:
#   1. tokenize the real example file and print every token
#   2. confirm an invalid character raises LexError with line/col
#   3. confirm a string literal produces a STRING_LIT token
#
# Run from the project root:  python tests/test_lexer.py

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow.lexer import tokenize
from agentflow.errors import LexError


def main():
    example_path = os.path.join(
        os.path.dirname(__file__), "..", "examples", "order_processor.aflow"
    )
    with open(example_path, "r", encoding="utf-8") as f:
        source = f.read()

    tokens = tokenize(source)
    for tok in tokens:
        print(tok)
    print()
    print("total tokens:", len(tokens))

    print()
    print("--- invalid character test ---")
    try:
        tokenize("state Charge { fee = 5# 3 }")
        print("ERROR: expected LexError, got none")
    except LexError as e:
        print("LexError caught:", e)

    print()
    print("--- string literal test ---")
    src = 'workflow W { state S entry { to = "hello@example.com"; } }'
    for tok in tokenize(src):
        print(tok)

    print()
    print("--- keyword case-sensitivity test ---")
    # PascalCase words that happen to equal a keyword must lex as ID, not
    # as the keyword, so states can be named `On`, `Exit`, `State`, etc.
    kinds = {t.value: t.type for t in tokenize("workflow W { state On; state Exit exit; }")}
    assert kinds["On"] == "ID", "expected On to lex as ID, got %s" % kinds["On"]
    assert kinds["Exit"] == "ID", "expected Exit to lex as ID, got %s" % kinds["Exit"]
    assert kinds["exit"] == "EXIT", "expected lowercase exit to stay a keyword"
    assert kinds["workflow"] == "WORKFLOW", "expected lowercase workflow to stay a keyword"
    print("PASS: PascalCase On/Exit lex as ID; lowercase keywords still match")


if __name__ == "__main__":
    main()
