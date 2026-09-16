# agentflow/__main__.py
#
# Command-line entry point for the AgentFlow compiler.
#
#   python -m agentflow <file.aflow> [options]
#
# Options:
#   --ast           print the parsed AST
#   --ir            print the generated IR
#   --optimized-ir  print the IR after optimization
#   --run           run the IR through the interpreter (with mocked agents)
#   --trace         with --run, print the verbose trace (implies --run)
#   --emit-python   print generated LangGraph-style Python
#   --write-python <path>   write generated Python to a file
#   --quiet         only print errors
#
# With no options, runs the full pipeline: lex, parse, analyze, generate
# IR, optimize, and print a short summary.

import sys
import os

from . import lexer, parser, semantic
from .ir_gen import IRGenerator
from .optimizer import Optimizer
from .interpreter import Interpreter
from .codegen_langgraph import LangGraphCodegen
from .errors import AgentFlowError
from .ast_nodes import AgentDeclNode


def _default_mock(_name):
    """A mock that always returns True, which routes 'on success'
    transitions. Enough for the demo to follow the happy path."""

    def _mock(_args):
        return True

    return _mock


def _read_source(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _usage():
    print(__doc__.strip())
    sys.exit(2)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0].startswith("-"):
        _usage()

    source_path = argv[0]
    opts = set(a for a in argv[1:] if a.startswith("--"))

    write_python_path = None
    if "--write-python" in argv:
        i = argv.index("--write-python")
        if i + 1 >= len(argv):
            print("error: --write-python needs a path")
            sys.exit(2)
        write_python_path = argv[i + 1]

    try:
        source = _read_source(source_path)
    except OSError as e:
        print("error: could not read %s: %s" % (source_path, e))
        sys.exit(1)

    quiet = "--quiet" in opts

    try:
        # ---- lexical ----
        tokens = lexer.tokenize(source)

        # ---- syntax ----
        program = parser.parse(tokens)

        # ---- semantic ----
        analyzer = semantic.SemanticAnalyzer()
        ok = analyzer.analyze(program)
        if not ok:
            print("Semantic errors:", file=sys.stderr)
            for err in analyzer.errors:
                print("  " + str(err), file=sys.stderr)
            sys.exit(1)

        # ---- IR ----
        ir = IRGenerator().generate(program)
        ir_count_before = len(ir.instructions)

        # ---- optimize ----
        optimizer = Optimizer()
        optimized = optimizer.optimize(ir)

        if not quiet:
            print("=== %s ===" % source_path)
            print("tokens:  %d" % len(tokens))
            print("states:  %d" % len(optimized.labels))
            print(
                "IR:      %d instructions (was %d before optimization)"
                % (len(optimized.instructions), ir_count_before)
            )
            print()

        if "--ast" in opts:
            print("=== AST ===")
            parser.describe(program)
            print()

        if "--ir" in opts:
            print("=== IR (unoptimized) ===")
            print(ir)
            print()

        if "--optimized-ir" in opts:
            print("=== IR (optimized) ===")
            print(optimized)
            print("optimizer stats:", optimizer.stats)
            print()

        if "--run" in opts or "--trace" in opts:
            # Build one mock per agent that the workflow actually declares.
            # Deterministic, no __missing__ tricks.
            mocks = {}
            for decl in program.decls:
                if isinstance(decl, AgentDeclNode):
                    mocks[decl.name] = _default_mock(decl.name)

            interp = Interpreter(mock_agents=mocks)
            verbose = "--trace" in opts
            try:
                final = interp.run(optimized, verbose=verbose)
            except AgentFlowError as e:
                print("runtime error:", e, file=sys.stderr)
                sys.exit(1)

            if verbose:
                for line in interp.trace:
                    print(line)
                print()

            print("=== interpreter result ===")
            for k in sorted(final.keys()):
                print("  %s = %r" % (k, final[k]))
            print()

        if "--emit-python" in opts:
            codegen = LangGraphCodegen()
            code = codegen.generate(program, optimized, source_name=source_path)
            print("=== generated LangGraph-style Python ===")
            print(code)

        if write_python_path:
            codegen = LangGraphCodegen()
            code = codegen.generate(program, optimized, source_name=source_path)
            with open(write_python_path, "w", encoding="utf-8") as f:
                f.write(code)
            print("wrote:", os.path.abspath(write_python_path))

        return 0

    except AgentFlowError as e:
        print("error:", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
