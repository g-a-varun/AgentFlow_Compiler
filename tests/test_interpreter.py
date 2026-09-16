# tests/test_interpreter.py
#
# Targeted tests for the interpreter, isolated from the rest of the
# pipeline. These cover operand resolution, string literals, the error
# paths, and both branch outcomes -- cases the end-to-end IR test does
# not exercise.
#
# The interpreter is built directly against an IRProgram, without going
# through the lexer/parser, so each test says exactly what it means.
#
# Run from the project root:  python tests/test_interpreter.py

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow.ir import IRProgram
from agentflow.interpreter import Interpreter
from agentflow.errors import IRError

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        print("PASS:", name)
        PASS += 1
    else:
        print("FAIL:", name)
        if detail:
            print("      " + detail)
        FAIL += 1


# ---- 1. basic arithmetic chain ----
prog = IRProgram("arith")
prog.set_label("Entry")
prog.entry = "Entry"
prog.emit("ENTER", ("Entry",))
prog.emit("ADD", ("t1", "2", "3"))
prog.emit("ASSIGN", ("x", "t1"))
prog.emit("MUL", ("t2", "t1", "4"))
prog.emit("ASSIGN", ("y", "t2"))
prog.emit("HALT", ())

interp = Interpreter()
final = interp.run(prog)
check(
    "arithmetic chain produces x=5, y=20",
    final.get("x") == 5 and final.get("y") == 20,
    "got %r" % final,
)


# ---- 2. string literal resolution ----
prog2 = IRProgram("strings")
prog2.set_label("Entry")
prog2.entry = "Entry"
prog2.emit("ENTER", ("Entry",))
prog2.emit("ASSIGN", ("to", '"hello@example.com"'))
prog2.emit("HALT", ())
final2 = Interpreter().run(prog2)
check(
    "string literal stored without surrounding quotes",
    final2.get("to") == "hello@example.com",
    "got %r" % final2,
)


# ---- 3. branch on true goes to true_target ----
prog3 = IRProgram("branch_true")
prog3.set_label("Entry")
prog3.entry = "Entry"
prog3.emit("ENTER", ("Entry",))
prog3.emit("ASSIGN", ("flag", "1"))
prog3.emit("BRANCH", ("flag", "Yes", "No"))
prog3.set_label("Yes")
prog3.emit("ASSIGN", ("taken", "1"))
prog3.emit("HALT", ())
prog3.set_label("No")
prog3.emit("ASSIGN", ("taken", "0"))
prog3.emit("HALT", ())
final3 = Interpreter().run(prog3)
check(
    "branch on nonzero goes to true target", final3.get("taken") == 1, "got %r" % final3
)


# ---- 4. branch on false goes to false_target ----
prog4 = IRProgram("branch_false")
prog4.set_label("Entry")
prog4.entry = "Entry"
prog4.emit("ENTER", ("Entry",))
prog4.emit("ASSIGN", ("flag", "0"))
prog4.emit("BRANCH", ("flag", "Yes", "No"))
prog4.set_label("Yes")
prog4.emit("ASSIGN", ("taken", "1"))
prog4.emit("HALT", ())
prog4.set_label("No")
prog4.emit("ASSIGN", ("taken", "0"))
prog4.emit("HALT", ())
final4 = Interpreter().run(prog4)
check(
    "branch on zero goes to false target", final4.get("taken") == 0, "got %r" % final4
)


# ---- 5. branch with missing target halts cleanly ----
prog5 = IRProgram("branch_none")
prog5.set_label("Entry")
prog5.entry = "Entry"
prog5.emit("ENTER", ("Entry",))
prog5.emit("ASSIGN", ("flag", "0"))
prog5.emit("BRANCH", ("flag", "Yes", None))  # false target is None
prog5.set_label("Yes")
prog5.emit("HALT", ())
final5 = Interpreter().run(prog5)
check(
    "branch with None target halts without error",
    "flag" in final5 and final5["flag"] == 0,
    "got %r" % final5,
)


# ---- 6. division by zero raises IRError ----
prog6 = IRProgram("div0")
prog6.set_label("Entry")
prog6.entry = "Entry"
prog6.emit("ENTER", ("Entry",))
prog6.emit("DIV", ("t1", "10", "0"))
prog6.emit("HALT", ())
try:
    Interpreter().run(prog6)
    check("division by zero raises IRError", False, "no error raised")
except IRError as e:
    check(
        "division by zero raises IRError",
        "division by zero" in str(e),
        "wrong error: %s" % e,
    )


# ---- 7. missing mock raises IRError ----
prog7 = IRProgram("missing_mock")
prog7.set_label("Entry")
prog7.entry = "Entry"
prog7.emit("ENTER", ("Entry",))
prog7.emit("CALL", ("t1", "NoSuchAgent", ()))
prog7.emit("HALT", ())
try:
    Interpreter(mock_agents={}).run(prog7)
    check("missing mock raises IRError", False, "no error raised")
except IRError as e:
    check("missing mock raises IRError", "NoSuchAgent" in str(e), "wrong error: %s" % e)


# ---- 8. undefined variable at run time raises IRError ----
prog8 = IRProgram("undef")
prog8.set_label("Entry")
prog8.entry = "Entry"
prog8.emit("ENTER", ("Entry",))
prog8.emit("ASSIGN", ("x", "never_set"))  # 'never_set' looks like a var
prog8.emit("HALT", ())
try:
    Interpreter().run(prog8)
    check("undefined variable raises IRError", False, "no error raised")
except IRError as e:
    check(
        "undefined variable raises IRError",
        "never_set" in str(e),
        "wrong error: %s" % e,
    )


print()
print("%d passed, %d failed" % (PASS, FAIL))
if FAIL:
    raise SystemExit(1)
