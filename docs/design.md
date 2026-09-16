# AgentFlow — System Design

This document describes how the compiler is put together and why.

## Pipeline

    .aflow source text
          |
          v
    +----------------+
    | lexer.py       |  text -> list of Token
    +----------------+
          |
          v
    +----------------+
    | grammar.py     |  (built at import time)
    |                |  grammar -> FIRST, FOLLOW, LR(0) states,
    |                |  ACTION/GOTO table, conflict check
    +----------------+
          |
          v
    +----------------+
    | parser.py      |  tokens + table -> AST
    +----------------+
          |
          v
    +----------------+
    | semantic.py    |  AST -> symbol table + type/structural checks
    +----------------+
          |
          v
    +----------------+
    | ir_gen.py      |  AST -> three-address IRProgram
    +----------------+
          |
          v
    +----------------+
    | optimizer.py   |  IR -> smaller IR
    +----------------+
          |
          +--------------------------+
          |                          |
          v                          v
    +----------------+        +---------------------+
    | interpreter.py |        | codegen_langgraph.py|
    | IR -> result   |        | IR -> Python source |
    +----------------+        +---------------------+

Every stage consumes the output of the previous one and nothing else.
No stage reaches back to look at an earlier stage's data.

## Module responsibilities

| Module                 | Consumes                    | Produces                                                                        | Owns                                 |
| ---------------------- | --------------------------- | ------------------------------------------------------------------------------- | ------------------------------------ |
| `tokens.py`            | —                           | `Token` class                                                                   | the shape of a single token          |
| `errors.py`            | —                           | `LexError`, `ParseError`, `SemanticError`, `IRError`                            | uniform error type with line/col     |
| `lexer.py`             | source text                 | `list[Token]`                                                                   | character-level scanning             |
| `grammar.py`           | —                           | `productions`, `FIRST`, `FOLLOW`, `states`, `action`, `goto_table`, `conflicts` | the grammar itself and the SLR table |
| `ast_nodes.py`         | —                           | node classes                                                                    | the shape of an AST node             |
| `parser.py`            | token list + SLR table      | `ProgramNode` (AST root)                                                        | shift-reduce loop, AST construction  |
| `symbol_table.py`      | —                           | `SymbolTable`                                                                   | scoping rules                        |
| `semantic.py`          | AST                         | bool + list of errors                                                           | every type and structure rule        |
| `ir.py`                | —                           | `Instruction`, `IRProgram`                                                      | IR instruction shape and label table |
| `ir_gen.py`            | AST                         | `IRProgram`                                                                     | lowering from tree to flat list      |
| `optimizer.py`         | `IRProgram`                 | `IRProgram` (mutated)                                                           | the three passes                     |
| `interpreter.py`       | `IRProgram` + mock agents   | result dict                                                                     | runtime semantics                    |
| `codegen_langgraph.py` | AST + optimized `IRProgram` | Python source string                                                            | translation to LangGraph-style code  |
| `__main__.py`          | CLI args                    | output                                                                          | wiring everything together           |

## Why the tables are built at import time

`grammar.py` runs its FIRST/FOLLOW/closure/goto loop at module import.
This means any module that does `from . import grammar` gets the whole
98-state SLR table ready to use. It costs about 100 milliseconds on the
example grammar — negligible — and it removes any need to have a
"build the tables" step in `__main__.py` or in tests.

The alternative — building tables lazily on first use — would add
complexity for no benefit at this grammar size.

## Why the IR is flat, not nested

Three-address code on paper is a flat sequence of instructions with
labels. Keeping the IR flat has three payoffs:

1. The optimizer is a single pass over `instructions`, no tree walking.
2. The interpreter is a `while` loop with a program counter — the same
   loop every textbook three-address interpreter uses.
3. The code generator can emit a function per block with no need to
   handle nested scopes.

If the IR were a tree of basic blocks, each of those three would need
its own traversal code.

## Why labels live in a separate dict

An `IRProgram` has `instructions: list` and `labels: dict[str, int]`.
The alternative — inserting `LABEL` pseudo-instructions — would force
every pass to skip them, and every index in the interpreter to be
off by one relative to the source. Keeping labels as a dict of
`name -> index` means the instruction list is dense and passes stay
simple.

The one cost: renaming or removing a block requires rebuilding the
labels dict, which `optimizer.py` does after both dead-state elimination
and branch-chain collapsing.

## Two backends, one IR

`interpreter.py` and `codegen_langgraph.py` both consume the same IR.
This is what the report claims when it says "the IR is target-agnostic".
Concretely:

- Both backends agree on the meaning of every opcode (`ASSIGN`, `ADD`,
  `SUB`, `MUL`, `DIV`, `CALL`, `JUMP`, `BRANCH`, `ENTER`, `HALT`).
- Adding a new backend means writing one file that switches on `instr.op`;
  neither the parser, the semantic analyzer, nor the IR generator changes.

The LangGraph backend is validated via `ast.parse()` and `compile()`
but never executed — LangGraph is not a dependency of the compiler. The
interpreter backend is what actually runs the example in tests and demos.

## The optimizer mutates in place

`Optimizer.optimize(program)` returns the same `IRProgram` object it
was given, mutated. This is a deliberate choice for the demo: it makes
the "before / after" story simple to tell, since you can hold a
reference to the program and see it shrink. The tradeoff is that you
must capture any "before" numbers (like instruction count) before
calling `optimize`. The CLI and the end-to-end test both do this.

## Error handling at every stage

Every stage raises a specific error class from `errors.py`, always with
a line and column (except `IRError`, which is a runtime condition and
has no source position). The CLI catches `AgentFlowError` once at the
top level and exits with status 1 on any error, so a single `try` /
`except` covers the whole pipeline.

The semantic analyzer is the exception to "raise on first error": it
collects every error it finds into `self.errors` and returns `False`
if the list is non-empty. That is what makes the
`invalid_semantic.aflow` example report four problems in one run.

## File-level conventions

- Every module has a comment block at the top explaining what it does
  and why, in plain English, before any code.
- No module imports from a later stage. `parser.py` does not know about
  IR; `ir_gen.py` does not know about the optimizer.
- Every AST node and IR instruction carries `line` and `col` from the
  source, even if the current stage never uses them — the next stage
  or a future error message might.
