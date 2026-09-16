# scripts/run_demo.py
#
# One-command demo of the whole AgentFlow pipeline on the real example.
# Shows each compiler stage in order: lex, parse, semantic, IR,
# optimize, interpret, and code generation.
#
# Run from the project root:
#     python scripts/run_demo.py
#
# Or pass a different .aflow file:
#     python scripts/run_demo.py examples/invalid_lex.aflow
#
# This script intentionally calls into the compiler package directly
# (rather than shelling out to `python -m agentflow`) so the reader can
# see exactly which stage produces which output.

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow import lexer, parser, semantic
from agentflow.ir_gen import IRGenerator
from agentflow.optimizer import Optimizer
from agentflow.interpreter import Interpreter
from agentflow.codegen_langgraph import LangGraphCodegen
from agentflow.ast_nodes import AgentDeclNode
from agentflow.errors import AgentFlowError


def banner(text):
    print()
    print("=" * 68)
    print(text)
    print("=" * 68)


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "..", "examples", "order_processor.aflow"
            )
        )

    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        # 1. lex
        banner("1. LEXER  --  source -> tokens")
        tokens = lexer.tokenize(source)
        print("tokens produced: %d" % len(tokens))
        print("first five:")
        for tok in tokens[:5]:
            print("   ", tok)

        # 2. parse
        banner("2. PARSER  --  tokens -> AST")
        program = parser.parse(tokens)
        print("workflow:", program.name)
        print("declarations:", len(program.decls))
        print()
        parser.describe(program)

        # 3. semantic
        banner("3. SEMANTIC ANALYSIS")
        analyzer = semantic.SemanticAnalyzer()
        ok = analyzer.analyze(program)
        if not ok:
            print("semantic errors:")
            for err in analyzer.errors:
                print("   ", err)
            return 1
        print("clean -- no semantic errors")

        # 4. IR
        banner("4. IR GENERATION  --  AST -> three-address code")
        ir = IRGenerator().generate(program)
        before = len(ir.instructions)
        print(ir)

        # 5. optimize
        banner("5. OPTIMIZER")
        optimizer = Optimizer()
        optimized = optimizer.optimize(ir)
        print(optimized)
        print()
        print("instructions: %d -> %d" % (before, len(optimized.instructions)))
        print("stats:", optimizer.stats)

        # 6. interpret
        banner("6. INTERPRETER  --  run IR with mocked agents")
        mocks = {}
        for decl in program.decls:
            if isinstance(decl, AgentDeclNode):
                mocks[decl.name] = lambda _args: True
        interp = Interpreter(mock_agents=mocks)
        final = interp.run(optimized, verbose=False)
        print("final variables:")
        for k in sorted(final.keys()):
            print("   %s = %r" % (k, final[k]))

        # 7. codegen
        banner("7. CODE GENERATION  --  IR -> LangGraph-style Python")
        code = LangGraphCodegen().generate(program, optimized, source_name=path)
        print("generated %d lines of Python" % len(code.splitlines()))
        print("(first 20 lines shown; full file written to examples/)")
        print()
        for line in code.splitlines()[:20]:
            print("   ", line)

        return 0

    except AgentFlowError as e:
        print()
        print("compilation failed:")
        print("   ", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
