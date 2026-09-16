# Phase Notes

A short log of what was built, in what order, and what was learned
along the way. Useful for the report's methodology section and for
answering viva questions about design decisions.

## Phase 1 — problem definition, grammar, prototype

**Order of work.**

1. Wrote the first grammar with just declarations and no expressions.
   Realized this was too shallow for a compiler project.
2. Added action blocks with assignments and arithmetic so the parser
   has to handle operator precedence and the semantic analyzer has to
   check types.
3. Wrote a program to build the LR(0) item sets and the SLR table
   mechanically. Running it on the grammar surfaced two bugs that
   reading the grammar by hand had missed:
   - The token `NUMBER` was being used both for the type keyword and
     for numeric literals like `100`. Split into `NUMBER` and `NUM`.
   - One production required a semicolon after a closing brace, which
     the example workflow did not have. Split `StateDecl` into two
     alternatives, one for the semicolon case and one for the brace case.
4. With both bugs fixed, the table generator reported 98 LR(0) states
   with zero shift-reduce or reduce-reduce conflicts.

**Lexer.** Written character by character, no regex, no lexer generator.
On the example workflow it produces 142 tokens with no errors, and it
correctly reports an unexpected character with its line and column.

**Deliverables at end of Phase 1.** Grammar, verified table, lexer,
initial prototype. Sections 10.1 through 10.3 of the phase report
hold the real output.

## Phase 2 — parser, semantic analysis, IR, interpreter

**Parser.** Table-driven SLR parser. It reads the ACTION/GOTO table
from `grammar.py` and drives the standard shift-reduce loop. AST nodes
are built as a side effect of every reduce, matching syntax-directed
translation as described in the course text.

**String literal gap.** The original grammar had no way to write a
string value in an action block, even though `string` was a valid
parameter type for tools like `SendEmail`. Added a `STRING_LIT` token
to the lexer and a `Factor -> STRING_LIT` production to the grammar,
then re-verified: 98 states (one more than before), still 0 conflicts.

**Semantic analysis.** The analyzer does more than type checking: it
also validates the workflow structure (single entry, at least one exit,
reachability from the entry, bounded outcome dispatch), the
bind-or-action exclusivity rule, and the call arity and argument types.
The two-tier symbol table (global for tools/agents/states, per-state
local for action-block variables) is what makes scope isolation between
states fall out with no extra code — resetting the local scope before
each state catches both genuine use-before-assignment and cross-state
leakage through the same code path.

**Intermediate code.** Three-address IR: flat instruction list, labels
as a dict of name-to-index, operands as strings (numeric literals,
quoted string literals, or variable names). Every arithmetic
subexpression lowers to its own temp, which is what the optimizer
later folds.

**Interpreter.** Runs the IR directly against mocked agents. Because
the agents are mocked, the whole thing runs offline with no API keys —
one of the two backends the report promises.

## Phase 3 — optimizer, code generation, tests

**Optimizer.** Three passes:

- Constant folding: any arithmetic instruction whose operands are both
  numeric literals becomes a single `ASSIGN`. On the example workflow,
  `ADD t2, 2, 3` becomes `ASSIGN t2, 5`.
- Dead-state elimination: BFS from the entry state over JUMP/BRANCH
  edges; any labelled block not reached is dropped.
- Branch-chain collapsing: a block that is exactly `[ENTER X, JUMP Y]`
  is a pass-through; every jump or branch that targeted it is redirected
  to Y and the block is removed. On the example workflow, the `Failed`
  state (which does nothing and just forwards to `Done`) is collapsed
  into `Done`, and both branches that used to go to `Failed` now go
  straight to `Done`.

On the example workflow: 18 instructions before optimization, 16 after.
One constant fold, one branch-chain collapse, zero unreachable blocks.

**Code generation.** IR to LangGraph-style Python. One function per
state, one router function per conditional branch, and a `build_graph()`
that wires them together. Generated code is validated via `ast.parse()`
and `compile()` at generation time; the compiler does not depend on
LangGraph being installed, and does not execute the output. This is
the second backend the report promises.

**Testing.** One test file per stage, plus an end-to-end test.

- `test_lexer.py`: tokenizes the example, checks invalid-character
  handling and string literal tokenization.
- `test_parser.py`: parses the example, checks operator precedence
  via `2 + 3 * 4`, checks a missing-semicolon parse error.
- `test_semantic.py`: 27 cases, one per semantic rule, plus the real
  example still parses cleanly.
- `test_ir.py`: IR generation, expected branch targets, expected
  interpreter path.
- `test_optimizer.py`: constant folding visible in the output, branch
  collapsing removes `Failed` as a target, no increase in instruction
  count, optimized IR still runs.
- `test_codegen.py`: generated Python parses and compiles, structural
  pieces present, optimizer effects visible in the output.
- `test_end_to_end.py`: the whole pipeline in one test.

## What is not done (deliberate, documented cuts)

- Nested `if` inside action blocks. The keyword is reserved in the
  lexer, but there is no production that uses it.
- General boolean expressions in transition conditions. Kept to
  bounded outcome labels (`on success`, `on failure`), because the
  domain outcome is boolean by construction.
- Constant propagation beyond literal-literal folding. A variable set
  to a literal and later used in arithmetic is not folded.
- Register allocation or temporary reuse in the IR. Each temporary is
  single-assignment by design, which keeps the optimizer and the
  interpreter simple.
- User-defined recursive procedures. The domain has no such concept.
