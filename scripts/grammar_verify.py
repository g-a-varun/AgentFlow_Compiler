# scripts/grammar_verify.py
#
# Reports on the SLR(1) table built in agentflow/grammar.py: how many
# states it has, whether it has any shift-reduce or reduce-reduce
# conflicts, and a few FOLLOW sets worth showing.
#
# Run from the project root:  python scripts/grammar_verify.py

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow import grammar

print("Terminals (%d): %s" % (len(grammar.terminals), sorted(grammar.terminals)))
print(
    "Nonterminals (%d): %s" % (len(grammar.nonterminals), sorted(grammar.nonterminals))
)
print("LR(0) states: %d" % len(grammar.states))
print("Total ACTION/GOTO cells: %d" % (len(grammar.action) + len(grammar.goto_table)))
print()
print("Selected FOLLOW sets:")
for nt in [
    "DeclList",
    "Decl",
    "Action",
    "Expr",
    "Term",
    "Factor",
    "ArgListOpt",
    "ParamListOpt",
]:
    print("  FOLLOW(%s) = %s" % (nt, sorted(grammar.FOLLOW[nt])))
print()
if grammar.conflicts:
    print("CONFLICTS FOUND: %d" % len(grammar.conflicts))
    for c in grammar.conflicts:
        sid, sym, old, new, pstr = c
        print(
            "  State %d, lookahead %r: %s vs %s  (from reducing %s)"
            % (sid, sym, old, new, pstr)
        )
    raise SystemExit(1)
else:
    print("NO CONFLICTS. Grammar is SLR(1) as specified.")
