# tests/test_codegen.py
#
# Generates LangGraph-style Python from the example workflow's optimized
# IR, checks that the result is valid Python via ast.parse and compile,
# checks specific structural pieces are present, and writes the
# generated file to a temp path (a committed copy lives in examples/).
#
# Run from the project root:  python tests/test_codegen.py

import sys
import os
import ast

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow import lexer, parser
from agentflow.ir_gen import IRGenerator
from agentflow.optimizer import Optimizer
from agentflow.codegen_langgraph import LangGraphCodegen


def main():
    example_path = os.path.join(
        os.path.dirname(__file__), "..", "examples", "order_processor.aflow"
    )
    with open(example_path, "r", encoding="utf-8") as f:
        source = f.read()

    ast_node = parser.parse(lexer.tokenize(source))
    ir = IRGenerator().generate(ast_node)
    ir = Optimizer().optimize(ir)

    codegen = LangGraphCodegen()
    code = codegen.generate(ast_node, ir, source_name="examples/order_processor.aflow")

    print("=== generated Python ===")
    print(code)
    print()

    print("=== validation ===")

    # 1. ast.parse on the whole text
    ast.parse(code)
    print("PASS: ast.parse() accepted the generated code")

    # 2. compile() as a stronger check
    compile(code, "<generated>", "exec")
    print("PASS: compile() accepted the generated code")

    # 3. structural checks
    expected = [
        "def state_Start(state):",
        "def state_CheckStock(state):",
        "def state_Charge(state):",
        "def state_Notify(state):",
        "def state_Done(state):",
        "def route_CheckStock(state):",
        "def route_Charge(state):",
        "def InventoryAgent(state, *args):",
        "def PaymentAgent(state, *args):",
        "def NotifierAgent(state, *args):",
        'graph.set_entry_point("Start")',
        'graph.add_node("Charge", state_Charge)',
        'graph.add_edge("Start", "CheckStock")',
        'graph.add_conditional_edges("CheckStock", route_CheckStock',
        'graph.add_edge("Done", END)',
        "return graph.compile()",
        "app = build_graph()",
    ]
    for needle in expected:
        assert needle in code, "missing from generated code: %r" % needle
    print("PASS: expected structural pieces are present")

    # 4. optimizer effect should be visible: Failed is gone
    assert "def state_Failed" not in code, (
        "optimizer removed Failed, but codegen still emitted it"
    )
    print("PASS: optimized-away Failed block is not in generated code")

    # 5. constant folding effect should be visible: '2 + 3' does not appear
    assert "2 + 3" not in code, "constant folding did not survive into codegen"
    assert 'out["t2"] = 5' in code, (
        "expected the folded literal 5 in the generated code"
    )
    print("PASS: constant folding is visible in generated code")

    # 6. write the artifact to a throwaway temp file. A committed copy of
    #    this output lives at examples/order_processor_generated.py as
    #    evidence; the test deliberately does NOT overwrite it, so running
    #    the suite never dirties the working tree.
    import tempfile

    out_path = os.path.join(tempfile.gettempdir(), "order_processor_generated.py")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(code)
    print("wrote (temp):", out_path)


if __name__ == "__main__":
    main()
