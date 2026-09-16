# AgentFlow

A compiler for a small domain-specific language that describes AI agent
workflows. You write a `.aflow` file with states, transitions, tools, and
agents; the compiler validates it and either generates LangGraph-style
Python or runs it directly against mocked agents.

This is the BCSE307P Compiler Design Laboratory project.

## Layout

    agentflow/          the compiler package
      tokens.py         Token class
      errors.py         LexError, ParseError, SemanticError, IRError
      lexer.py          hand-written tokenizer
      grammar.py        grammar + LR(0)/SLR table construction
      ast_nodes.py      AST node classes
      parser.py         table-driven SLR parser
      symbol_table.py   global + per-state local symbol table
      semantic.py       type checking, reachability, structural checks
      ir.py             three-address IR data structures
      ir_gen.py         AST -> IR
      optimizer.py      constant folding, dead-state elim., branch collapsing
      interpreter.py    IR interpreter with mocked agents
      codegen_langgraph.py   IR -> LangGraph-style Python
      __main__.py       CLI entry point

    examples/           sample .aflow files (valid + three broken ones)
    tests/              one test file per compiler stage
    scripts/            grammar_verify.py, smoke_test.py
    docs/               grammar.md, design.md
    reports/            phase reports

## Running

From the project root:

    python -m agentflow examples/order_processor.aflow

Options:

    --ast            print the parsed AST
    --ir             print the IR before optimization
    --optimized-ir   print the IR after optimization
    --run            run the IR through the interpreter (mocked agents)
    --trace          with --run, print the verbose trace
    --emit-python    print generated LangGraph-style Python
    --write-python <path>   write the generated Python to a file
    --quiet          suppress the summary

## Tests

    python tests/test_lexer.py
    python tests/test_parser.py
    python tests/test_semantic.py
    python tests/test_ir.py
    python tests/test_optimizer.py
    python tests/test_codegen.py
    python tests/test_end_to_end.py
    python scripts/grammar_verify.py

## Compiler pipeline

    .aflow source
        |
        v
    lexer     -> Token list
        |
        v
    parser    -> AST  (SLR(1), table-driven)
        |
        v
    semantic  -> symbol table + checks
        |
        v
    ir_gen    -> three-address IR
        |
        v
    optimizer -> constant folding, dead-state elimination, branch collapsing
        |
        +--> codegen_langgraph -> Python (validated via ast.parse)
        |
        +--> interpreter       -> mocked-agent execution with trace

## No external dependencies

The compiler is pure Python 3.10+. LangGraph is _not_ installed; the
generated code is validated with `ast.parse()` and `compile()` but never
executed. The interpreter backend is what actually runs.
