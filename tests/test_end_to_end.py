# tests/test_end_to_end.py
#
# Runs the full pipeline on the real example: lexer -> parser ->
# semantic -> IR -> optimizer -> interpreter, and on the side verifies
# that codegen still produces valid Python from the same input.
#
# This is the test that proves the whole compiler is wired together.
#
# Run from the project root:  python tests/test_end_to_end.py

import ast
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow import lexer, parser, semantic
from agentflow.codegen_langgraph import LangGraphCodegen
from agentflow.interpreter import Interpreter
from agentflow.ir_gen import IRGenerator
from agentflow.optimizer import Optimizer


def main():
    example_path = os.path.join(
        os.path.dirname(__file__), "..", "examples", "order_processor.aflow"
    )
    with open(example_path, "r", encoding="utf-8") as f:
        source = f.read()

    print("=== pipeline ===")
    tokens = lexer.tokenize(source)
    print("1. lexer:    %d tokens" % len(tokens))

    program = parser.parse(tokens)
    print("2. parser:   %d declarations" % len(program.decls))

    analyzer = semantic.SemanticAnalyzer()
    ok = analyzer.analyze(program)
    assert ok, "semantic errors: %s" % [str(e) for e in analyzer.errors]
    print("3. semantic: clean")

    ir = IRGenerator().generate(program)
    before = len(ir.instructions)
    print("4. IR:       %d instructions" % before)

    optimizer = Optimizer()
    optimized = optimizer.optimize(ir)
    print(
        "5. optimize: %d -> %d instructions, stats=%s"
        % (before, len(optimized.instructions), optimizer.stats)
    )

    mocks = {
        "InventoryAgent": lambda args: True,
        "PaymentAgent": lambda args: True,
        "NotifierAgent": lambda args: None,
    }
    interp = Interpreter(mock_agents=mocks)
    final = interp.run(optimized, verbose=False)
    print("6. run:      final vars = %s" % final)
    assert final.get("fee") == 5
    assert final.get("total") == 100
    assert final.get("result") is True

    print()
    print("=== codegen sanity ===")
    codegen = LangGraphCodegen()
    code = codegen.generate(program, optimized, source_name=example_path)
    ast.parse(code)
    compile(code, "<generated>", "exec")
    print("codegen:     %d lines, ast.parse and compile OK" % len(code.splitlines()))

    print()
    print("END-TO-END PASS")


if __name__ == "__main__":
    main()
