# AgentFlow Grammar

This is the grammar exactly as it appears in `agentflow/grammar.py`.
It has been mechanically verified by `scripts/grammar_verify.py`:
**98 LR(0) states, 0 conflicts, SLR(1) as specified.**

## Terminals (31)

Keywords:
WORKFLOW TOOL AGENT USES STATE ENTRY EXIT TRANSITION ON BIND CALL

Type keywords:
STRING NUMBER BOOL VOID

Identifiers and literals:
ID identifier
NUM numeric literal, e.g. 100
STRING_LIT string literal, e.g. "hello@example.com"

Operators and punctuation:
ARROW -> ASSIGN = PLUS + MINUS - MUL \* DIV /
COLON : COMMA , SEMI ; LPAREN ( RPAREN )
LBRACE { RBRACE }

End of file:
EOF

Note the deliberate split of `NUMBER` (type keyword) from `NUM` (numeric
literal), and `STRING` (type keyword) from `STRING_LIT` (string literal).
The first was a bug fixed during grammar verification; the second was
added in Phase 2 alongside the lexer so string-typed tool parameters
could actually be passed arguments.

## Nonterminals (22)

    Program  Program'  DeclList  Decl
    ToolDecl  ParamListOpt  ParamList  Param  Type
    AgentDecl
    StateDecl  StateModOpt  ActionList  Action
    ArgListOpt  ArgList  Expr  Term  Factor
    TransitionDecl  TransCondOpt
    BindDecl

## Productions

    Program        -> WORKFLOW ID LBRACE DeclList RBRACE

    DeclList       -> DeclList Decl
                    | Decl

    Decl           -> ToolDecl
                    | AgentDecl
                    | StateDecl
                    | TransitionDecl
                    | BindDecl

    ToolDecl       -> TOOL ID LPAREN ParamListOpt RPAREN ARROW Type SEMI

    ParamListOpt   -> ParamList
                    | ε

    ParamList      -> ParamList COMMA Param
                    | Param

    Param          -> ID COLON Type

    Type           -> STRING | NUMBER | BOOL | VOID

    AgentDecl      -> AGENT ID USES ID SEMI

    StateDecl      -> STATE ID StateModOpt SEMI
                    | STATE ID StateModOpt LBRACE ActionList RBRACE

    StateModOpt    -> ENTRY | EXIT | ε

    ActionList     -> ActionList Action
                    | Action

    Action         -> ID ASSIGN Expr SEMI
                    | ID ASSIGN CALL ID LPAREN ArgListOpt RPAREN SEMI
                    | CALL ID LPAREN ArgListOpt RPAREN SEMI

    ArgListOpt     -> ArgList
                    | ε

    ArgList        -> ArgList COMMA Expr
                    | Expr

    Expr           -> Expr PLUS Term
                    | Expr MINUS Term
                    | Term

    Term           -> Term MUL Factor
                    | Term DIV Factor
                    | Factor

    Factor         -> NUM
                    | STRING_LIT
                    | ID
                    | LPAREN Expr RPAREN

    TransitionDecl -> TRANSITION ID ARROW ID TransCondOpt SEMI

    TransCondOpt   -> ON ID
                    | ε

    BindDecl       -> BIND ID COLON ID SEMI

## Design notes

**Hybrid declarative + imperative.** The top level (tools, agents, states,
transitions, binds) is declarative. The action block inside a state
(`{ fee = 2 + 3; total = 100; result = call PaymentAgent(total); }`) is
imperative: assignments, arithmetic with operator precedence, and calls.

**Expr / Term / Factor layering.** The three-level layering gives the
usual precedence and associativity: `2 + 3 * 4` parses as `2 + (3 * 4)`,
and `a - b - c` parses as `(a - b) - c`. The parser test asserts the
first explicitly.

**Two StateDecl alternatives.** A state either ends in `;` (no action
block) or in `}` after a brace-delimited action block (no `;` after the
brace). This matches the example workflow. The alternative is that a
`;` after `}` would have been required, which the example did not have —
one of the two grammar bugs found during verification.

**Bounded outcome labels.** Transition conditions are `on <id>` where the
id is a bare name. There is no general boolean expression. The grammar
accepts any identifier after `on`, but the semantic analyzer enforces the
real rule: a conditioned transition must route on `success` or `failure`
and no other label, each outcome may be used at most once, a state may not
mix a conditioned transition with an unconditioned one, and a state may
have at most one unconditioned transition. It also checks that a state
with a conditioned transition can actually resolve a boolean outcome (a
bind to a bool-returning tool, or an action block ending in a
bool-returning call). Anything else is reported as an error instead of
producing a transition that can never be taken.

**Not in the grammar (deliberate cuts).**

- Nested `if` inside action blocks (the `if` keyword is reserved in the
  lexer, but no production uses it).
- String operations: a string literal can be passed as an argument, but
  no concatenation or comparison.
- Explicit return statements, loops, or user-defined procedures.
