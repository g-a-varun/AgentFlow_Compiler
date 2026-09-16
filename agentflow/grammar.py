# agentflow/grammar.py
#
# The AgentFlow grammar and the SLR(1) parsing table built from it:
# FIRST sets, FOLLOW sets, the LR(0) canonical collection (closure and
# goto), and the ACTION/GOTO table.
#
# Running this file with `import agentflow.grammar` builds the whole
# table at import time and leaves the results as module-level names:
#   productions, terminals, nonterminals, FIRST, FOLLOW,
#   states, action, goto_table, conflicts
#
# Terminals are plain strings that match the token types produced by
# agentflow/lexer.py, so the parser can look up the ACTION table
# directly with a token's .type without any conversion.

EPS = "ε"
EOF = "$"


# Each production is (lhs, rhs_tuple). The very first entry below is the
# augmented start rule Program' -> Program, which is what lets the
# parser know when to accept.
productions_raw = [
    ("Program", ("WORKFLOW", "ID", "LBRACE", "DeclList", "RBRACE")),
    ("DeclList", ("DeclList", "Decl")),
    ("DeclList", ("Decl",)),
    ("Decl", ("ToolDecl",)),
    ("Decl", ("AgentDecl",)),
    ("Decl", ("StateDecl",)),
    ("Decl", ("TransitionDecl",)),
    ("Decl", ("BindDecl",)),
    (
        "ToolDecl",
        ("TOOL", "ID", "LPAREN", "ParamListOpt", "RPAREN", "ARROW", "Type", "SEMI"),
    ),
    ("ParamListOpt", ("ParamList",)),
    ("ParamListOpt", ()),
    ("ParamList", ("ParamList", "COMMA", "Param")),
    ("ParamList", ("Param",)),
    ("Param", ("ID", "COLON", "Type")),
    ("Type", ("STRING",)),
    ("Type", ("NUMBER",)),
    ("Type", ("BOOL",)),
    ("Type", ("VOID",)),
    ("AgentDecl", ("AGENT", "ID", "USES", "ID", "SEMI")),
    # StateDecl has two explicit alternatives: one terminated by SEMI, one
    # terminated by a brace-delimited action block (which has no SEMI after
    # it, matching the example program).
    ("StateDecl", ("STATE", "ID", "StateModOpt", "SEMI")),
    ("StateDecl", ("STATE", "ID", "StateModOpt", "LBRACE", "ActionList", "RBRACE")),
    ("StateModOpt", ("ENTRY",)),
    ("StateModOpt", ("EXIT",)),
    ("StateModOpt", ()),
    ("ActionList", ("ActionList", "Action")),
    ("ActionList", ("Action",)),
    ("Action", ("ID", "ASSIGN", "Expr", "SEMI")),
    (
        "Action",
        ("ID", "ASSIGN", "CALL", "ID", "LPAREN", "ArgListOpt", "RPAREN", "SEMI"),
    ),
    ("Action", ("CALL", "ID", "LPAREN", "ArgListOpt", "RPAREN", "SEMI")),
    ("ArgListOpt", ("ArgList",)),
    ("ArgListOpt", ()),
    ("ArgList", ("ArgList", "COMMA", "Expr")),
    ("ArgList", ("Expr",)),
    ("Expr", ("Expr", "PLUS", "Term")),
    ("Expr", ("Expr", "MINUS", "Term")),
    ("Expr", ("Term",)),
    ("Term", ("Term", "MUL", "Factor")),
    ("Term", ("Term", "DIV", "Factor")),
    ("Term", ("Factor",)),
    # NUM  = numeric literal, e.g. 100
    # STRING_LIT = string literal, e.g. "hello@example.com"
    # (These are separate from the type keywords NUMBER and STRING.)
    ("Factor", ("NUM",)),
    ("Factor", ("STRING_LIT",)),
    ("Factor", ("ID",)),
    ("Factor", ("LPAREN", "Expr", "RPAREN")),
    ("TransitionDecl", ("TRANSITION", "ID", "ARROW", "ID", "TransCondOpt", "SEMI")),
    ("TransCondOpt", ("ON", "ID")),
    ("TransCondOpt", ()),
    ("BindDecl", ("BIND", "ID", "COLON", "ID", "SEMI")),
]

START = "Program"
AUG_START = "Program'"
productions = [(AUG_START, (START,))] + productions_raw

nonterminals = set(p[0] for p in productions)
all_symbols = set()
for lhs, rhs in productions:
    all_symbols.add(lhs)
    all_symbols.update(rhs)
terminals = all_symbols - nonterminals


# ---------- FIRST sets ----------
FIRST = {t: {t} for t in terminals}
for nt in nonterminals:
    FIRST[nt] = set()


def first_of_seq(seq):
    result = set()
    nullable = True
    for sym in seq:
        f = FIRST[sym]
        result |= f - {EPS}
        if EPS not in f:
            nullable = False
            break
    if nullable:
        result.add(EPS)
    return result


changed = True
while changed:
    changed = False
    for lhs, rhs in productions:
        if len(rhs) == 0:
            if EPS not in FIRST[lhs]:
                FIRST[lhs].add(EPS)
                changed = True
        else:
            f = first_of_seq(rhs)
            before = len(FIRST[lhs])
            FIRST[lhs] |= f
            if len(FIRST[lhs]) != before:
                changed = True


# ---------- FOLLOW sets ----------
FOLLOW = {nt: set() for nt in nonterminals}
FOLLOW[AUG_START].add(EOF)

changed = True
while changed:
    changed = False
    for lhs, rhs in productions:
        for i, sym in enumerate(rhs):
            if sym in nonterminals:
                beta = rhs[i + 1 :]
                f_beta = first_of_seq(beta)
                before = len(FOLLOW[sym])
                FOLLOW[sym] |= f_beta - {EPS}
                if EPS in f_beta:
                    FOLLOW[sym] |= FOLLOW[lhs]
                if len(FOLLOW[sym]) != before:
                    changed = True


# ---------- LR(0) canonical collection ----------
def closure(items):
    items = set(items)
    added = True
    while added:
        added = False
        new_items = set()
        for pi, dot in items:
            lhs, rhs = productions[pi]
            if dot < len(rhs):
                sym = rhs[dot]
                if sym in nonterminals:
                    for j, (lhs2, rhs2) in enumerate(productions):
                        if lhs2 == sym and (j, 0) not in items:
                            new_items.add((j, 0))
        if new_items:
            items |= new_items
            added = True
    return frozenset(items)


def goto(items, sym):
    moved = set()
    for pi, dot in items:
        lhs, rhs = productions[pi]
        if dot < len(rhs) and rhs[dot] == sym:
            moved.add((pi, dot + 1))
    if not moved:
        return None
    return closure(moved)


initial = closure({(0, 0)})
states = [initial]
state_index = {initial: 0}
transitions = {}

worklist = [0]
while worklist:
    sid = worklist.pop()
    items = states[sid]
    symbols_after_dot = set()
    for pi, dot in items:
        lhs, rhs = productions[pi]
        if dot < len(rhs):
            symbols_after_dot.add(rhs[dot])
    for sym in symbols_after_dot:
        target = goto(items, sym)
        if target is None:
            continue
        if target not in state_index:
            state_index[target] = len(states)
            states.append(target)
            worklist.append(state_index[target])
        transitions[(sid, sym)] = state_index[target]


# ---------- SLR table + conflict detection ----------
action = {}
goto_table = {}
conflicts = []


def prod_str(pi):
    lhs, rhs = productions[pi]
    return "%s -> %s" % (lhs, " ".join(rhs) if rhs else EPS)


for sid, items in enumerate(states):
    for pi, dot in items:
        lhs, rhs = productions[pi]
        if dot < len(rhs):
            sym = rhs[dot]
            if sym in terminals:
                target = transitions.get((sid, sym))
                if target is not None:
                    key = (sid, sym)
                    new_action = ("shift", target)
                    if key in action and action[key] != new_action:
                        conflicts.append(
                            (sid, sym, action[key], new_action, prod_str(pi))
                        )
                    action[key] = new_action
            else:
                target = transitions.get((sid, sym))
                if target is not None:
                    goto_table[(sid, sym)] = target
        else:
            if lhs == AUG_START:
                key = (sid, EOF)
                new_action = ("accept",)
                if key in action and action[key] != new_action:
                    conflicts.append((sid, EOF, action[key], new_action, prod_str(pi)))
                action[key] = new_action
            else:
                for a in FOLLOW[lhs]:
                    key = (sid, a)
                    new_action = ("reduce", pi)
                    if key in action and action[key] != new_action:
                        conflicts.append(
                            (sid, a, action[key], new_action, prod_str(pi))
                        )
                    action[key] = new_action
