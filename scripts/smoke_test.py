# scripts/smoke_test.py
#
# Quick check that the foundational modules import cleanly.
# Run from the project root:  python scripts/smoke_test.py

import os
import sys

# Make the project root importable, so `import agentflow` works no matter
# where this script is run from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow.errors import IRError, LexError, ParseError, SemanticError
from agentflow.tokens import Token

print(Token("ID", "OrderProcessor", 1, 1))
print(LexError("unexpected character #", 2, 13))
print(ParseError("unexpected STATE", 3, 5))
print(SemanticError("'x' is used before it is assigned", 2, 9))
print(IRError("no rule for opcode CALL"))
