# tests/test_optimizer.py
#
# Runs the optimizer on the real example and checks:
#   1. 2 + 3 gets constant-folded to an ASSIGN ..., 5
#   2. Failed (a no-op pass-through) is collapsed away as a branch target
#   3. The optimizer does not increase the instruction count
#   4. The interpreter produces the same result on the optimized IR
#
# Run from the project root:  python tests/test_optimizer.py

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow import lexer, parser
from agentflow.ir_gen import IRGenerator
from agentflow.optimizer import Optimizer
from agentflow.interpreter import Interpreter


def main():
    example_path = os.path.join(
        os.path.dirname(__file__), "..", "examples", "order_processor.aflow"
    )
    with open(example_path, "r", encoding="utf-8") as f:
        source = f.read()

    ast = parser.parse(lexer.tokenize(source))
    ir = IRGenerator().generate(ast)

    print("=== IR before optimization ===")
    print(ir)
    print()
    print("instruction count:", len(ir.instructions))
    print("label count:", len(ir.labels))
    print()

    optimizer = Optimizer()
    optimized = optimizer.optimize(ir)

    print("=== IR after optimization ===")
    print(optimized)
    print()
    print("instruction count:", len(optimized.instructions))
    print("label count:", len(optimized.labels))
    print()
    print("stats:", optimizer.stats)
    print()

    # --- assertions ---

    # 1. Constant folding: the ADD 2, 3 should be gone
    has_add_23 = any(
        i.op == "ADD" and i.args[1] == "2" and i.args[2] == "3"
        for i in optimized.instructions
    )
    assert not has_add_23, "ADD 2, 3 should have been constant-folded away"
    has_assign_5 = any(
        i.op == "ASSIGN" and i.args[1] == "5" for i in optimized.instructions
    )
    assert has_assign_5, "expected ASSIGN ..., 5 after folding 2 + 3"
    print("PASS: 2 + 3 was constant-folded to 5")

    # 2. Branch-chain collapsing: Failed should no longer appear as a target
    branch_targets = set()
    for instr in optimized.instructions:
        if instr.op == "BRANCH":
            _, t, f = instr.args
            if t is not None:
                branch_targets.add(t)
            if f is not None:
                branch_targets.add(f)
        elif instr.op == "JUMP":
            branch_targets.add(instr.args[0])
    assert "Failed" not in branch_targets, "Failed should have been collapsed into Done"
    print("PASS: branch-chain collapsing removed Failed as a target")

    # 3. No increase in instruction count
    assert len(optimized.instructions) <= len(ir.instructions)
    print("PASS: optimizer did not increase instruction count")

    # 4. Same result from the interpreter on the optimized IR
    interp = Interpreter(
        mock_agents={
            "InventoryAgent": lambda args: True,
            "PaymentAgent": lambda args: True,
            "NotifierAgent": lambda args: None,
        }
    )
    vars = interp.run(optimized, verbose=False)
    assert vars.get("result") is True
    assert vars.get("fee") == 5
    assert vars.get("total") == 100
    print("PASS: interpreter still runs the optimized IR correctly")


if __name__ == "__main__":
    main()
