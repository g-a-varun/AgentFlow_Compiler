# tests/test_ir.py
#
# Checks that IR generation and interpretation work end-to-end on the
# real example, plus a couple of small hand-checked cases:
#   1. IR is generated for order_processor.aflow
#   2. running it with mock agents follows the expected path:
#        Start -> CheckStock -> Charge -> Notify -> Done
#   3. constant-folding input is visible in the IR (fee = 2 + 3)
#
# Run from the project root:  python tests/test_ir.py

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow import lexer, parser
from agentflow.ir_gen import IRGenerator
from agentflow.interpreter import Interpreter


def main():
    example_path = os.path.join(
        os.path.dirname(__file__), "..", "examples", "order_processor.aflow"
    )
    with open(example_path, "r", encoding="utf-8") as f:
        source = f.read()

    ast = parser.parse(lexer.tokenize(source))

    gen = IRGenerator()
    ir = gen.generate(ast)

    print("=== IR program for %s ===" % ir.name)
    print("entry:", ir.entry)
    print()
    print(ir)
    print()

    # --- run it with mocked agents ---
    # Every call is documented here so the expected trace is obvious:
    #   InventoryAgent:  always succeeds (bool True)  -> route on success
    #   PaymentAgent:    always succeeds (bool True)  -> route on success
    #   NotifierAgent:   void (None)
    def inv(args):
        print("  [mock] InventoryAgent called, args=%r -> True" % (args,))
        return True

    def pay(args):
        print("  [mock] PaymentAgent called, args=%r -> True" % (args,))
        return True

    def notify(args):
        print("  [mock] NotifierAgent called, args=%r -> None" % (args,))
        return None

    interp = Interpreter(
        mock_agents={
            "InventoryAgent": inv,
            "PaymentAgent": pay,
            "NotifierAgent": notify,
        }
    )

    print("=== verbose trace ===")
    vars = interp.run(ir, verbose=True)
    for line in interp.trace:
        print(line)
    print()
    print("final variables:", vars)
    print()

    # --- assertions ---
    # 1. The IR should include a branch on CheckStock's outcome to Charge
    #    and to Failed, and a branch on Charge's outcome to Notify / Failed.
    branch_targets = set()
    for instr in ir.instructions:
        if instr.op == "BRANCH":
            _, tt, ft = instr.args
            branch_targets.add((tt, ft))
    assert ("Charge", "Failed") in branch_targets, (
        "CheckStock should branch to (Charge, Failed)"
    )
    assert ("Notify", "Failed") in branch_targets, (
        "Charge should branch to (Notify, Failed)"
    )
    print("PASS: expected BRANCH targets are present in the IR")

    # 2. The interpreter should have visited Notify (success path) and
    #    not Failed.
    joined_trace = "\n".join(interp.trace)
    assert "ENTER Notify" in joined_trace, "expected to enter Notify on success path"
    assert "ENTER Failed" not in joined_trace, "should not have entered Failed"
    print("PASS: interpreter followed the success path (Notify, not Failed)")

    # 3. The IR should contain the three-address form for 'fee = 2 + 3'
    #    BEFORE optimization (ADD t, 2, 3 then ASSIGN fee, t)
    has_add = any(
        i.op == "ADD" and i.args[1] == "2" and i.args[2] == "3" for i in ir.instructions
    )
    assert has_add, "expected an ADD instruction for 2 + 3"
    print("PASS: fee = 2 + 3 lowered to a three-address ADD")

    # 4. The final result variable should be True (PaymentAgent's bool)
    assert vars.get("result") is True, "expected result=True from mocked PaymentAgent"
    print("PASS: result of PaymentAgent call is stored as expected")


if __name__ == "__main__":
    main()
