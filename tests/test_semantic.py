# tests/test_semantic.py
#
# One small workflow per rule in the spec: either it should be rejected
# with a specific error, or it should be accepted cleanly. Run with
# `python tests/test_semantic.py` -- prints PASS/FAIL for each case and
# a summary at the end.

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentflow import lexer, parser, semantic

PASS_COUNT = 0
FAIL_COUNT = 0


def run(source):
    tokens = lexer.tokenize(source)
    program = parser.parse(tokens)
    analyzer = semantic.SemanticAnalyzer()
    ok = analyzer.analyze(program)
    return ok, analyzer.errors


def expect_error(name, source, message_fragment):
    global PASS_COUNT, FAIL_COUNT
    ok, errors = run(source)
    joined = " | ".join(str(e) for e in errors)
    if not ok and any(message_fragment in str(e) for e in errors):
        print("PASS:", name)
        PASS_COUNT += 1
    else:
        print("FAIL:", name)
        print("      expected an error containing:", repr(message_fragment))
        print("      got:", "(no errors)" if ok else joined)
        FAIL_COUNT += 1


def expect_clean(name, source):
    global PASS_COUNT, FAIL_COUNT
    ok, errors = run(source)
    if ok:
        print("PASS:", name)
        PASS_COUNT += 1
    else:
        print(
            "FAIL:",
            name,
            "-- expected no errors, got:",
            " | ".join(str(e) for e in errors),
        )
        FAIL_COUNT += 1


# ---- duplicate declarations ----
expect_error(
    "duplicate tool name",
    """
workflow W {
    tool A() -> void;
    tool A() -> bool;
    state S entry;
    state Done exit;
    transition S -> Done;
}
""",
    "tool 'A' is already declared",
)

expect_error(
    "duplicate state name",
    """
workflow W {
    state S entry;
    state S exit;
    transition S -> S;
}
""",
    "state 'S' is already declared",
)

# ---- undeclared references ----
expect_error(
    "agent uses undeclared tool",
    """
workflow W {
    agent Ag uses Missing;
    state S entry;
    state Done exit;
    transition S -> Done;
}
""",
    "agent 'Ag' uses undeclared tool 'Missing'",
)

expect_error(
    "transition to undeclared state",
    """
workflow W {
    state S entry;
    transition S -> Nowhere;
}
""",
    "undeclared state 'Nowhere'",
)

expect_error(
    "bind to undeclared agent",
    """
workflow W {
    state S entry;
    state Done exit;
    transition S -> Done;
    bind S : NoSuchAgent;
}
""",
    "undeclared agent 'NoSuchAgent'",
)

expect_error(
    "duplicate bind for the same state",
    """
workflow W {
    tool T() -> bool;
    agent A1 uses T;
    agent A2 uses T;
    state S entry;
    state Done exit;
    transition S -> Done;
    bind S : A1;
    bind S : A2;
}
""",
    "already has a bind",
)

# ---- entry/exit structure ----
expect_error(
    "no entry state",
    """
workflow W {
    state S;
    state Done exit;
    transition S -> Done;
}
""",
    "no entry state",
)

expect_error(
    "two entry states",
    """
workflow W {
    state A entry;
    state B entry;
    state Done exit;
    transition A -> Done;
    transition B -> Done;
}
""",
    "more than one entry state",
)

expect_error(
    "no exit state",
    """
workflow W {
    state S entry;
    transition S -> S;
}
""",
    "no exit state",
)

# ---- reachability and dead ends ----
expect_error(
    "unreachable state",
    """
workflow W {
    state S entry;
    state Done exit;
    state Island;
    transition S -> Done;
}
""",
    "'Island' can never be reached",
)

expect_error(
    "dead end state",
    """
workflow W {
    state S entry;
    state Trap;
    state Done exit;
    transition S -> Trap;
}
""",
    "'Trap' has no outgoing transitions",
)

# ---- transition consistency ----
expect_error(
    "more than one unconditioned transition from a state",
    """
workflow W {
    state S entry;
    state A;
    state B exit;
    transition S -> A;
    transition S -> B;
    transition A -> B;
}
""",
    "more than one unconditioned transition",
)

expect_error(
    "mixing a conditioned and an unconditioned transition",
    """
workflow W {
    tool T() -> bool;
    agent A uses T;
    state S entry { r = call A(); }
    state X;
    state Done exit;
    transition S -> X on success;
    transition S -> Done;
    transition X -> Done;
}
""",
    "mixes a conditioned transition with an unconditioned one",
)

expect_error(
    "conditioned transition on an unknown outcome label",
    """
workflow W {
    tool T() -> bool;
    agent A uses T;
    state S entry { r = call A(); }
    state Done exit;
    transition S -> Done on retry;
}
""",
    "unknown outcome 'retry'",
)

expect_error(
    "two transitions on the same outcome label",
    """
workflow W {
    tool T() -> bool;
    agent A uses T;
    state S entry { r = call A(); }
    state X;
    state Y exit;
    transition S -> X on success;
    transition S -> Y on success;
    transition X -> Y;
}
""",
    "more than one transition on 'success'",
)

# ---- duplicate tool parameter ----
expect_error(
    "tool with two parameters of the same name",
    """
workflow W {
    tool T(x: number, x: bool) -> void;
    agent A uses T;
    state S entry;
    state Done exit;
    transition S -> Done;
    bind S : A;
}
""",
    "duplicate parameter 'x'",
)

# ---- a state that legitimately routes on both success and failure ----
expect_clean(
    "success and failure outcomes together are allowed",
    """
workflow W {
    tool T() -> bool;
    agent A uses T;
    state S entry { r = call A(); }
    state Ok exit;
    state Bad exit;
    transition S -> Ok on success;
    transition S -> Bad on failure;
}
""",
)

# ---- bind / action-block exclusivity ----
expect_error(
    "state has both bind and action block",
    """
workflow W {
    tool T() -> bool;
    agent A uses T;
    state S entry { r = call A(); }
    state Done exit;
    transition S -> Done;
    bind S : A;
}
""",
    "has both a bind and an action block",
)

# ---- outcome resolution ----
expect_error(
    "conditioned transition with no bind and no action block",
    """
workflow W {
    state S entry;
    state X;
    state Done exit;
    transition S -> X on success;
    transition X -> Done;
}
""",
    "no bind and no action block to resolve it",
)

expect_error(
    "conditioned transition but last statement is a bare void call, not an assignment",
    """
workflow W {
    tool T() -> void;
    agent A uses T;
    state S entry {
        call A();
    }
    state Done exit;
    transition S -> Done on success;
}
""",
    "does not end with a bool-returning call",
)

expect_error(
    "conditioned transition but last call returns number, not bool",
    """
workflow W {
    tool T() -> number;
    agent A uses T;
    state S entry {
        total = call A();
    }
    state Done exit;
    transition S -> Done on success;
}
""",
    "returns number, not bool",
)

expect_clean(
    "unconditioned transitions need no outcome, even with no bind/actions",
    """
workflow W {
    state S entry;
    state Done exit;
    transition S -> Done;
}
""",
)

# ---- type checking on calls ----
expect_error(
    "call arity mismatch",
    """
workflow W {
    tool T(x: number) -> bool;
    agent A uses T;
    state S entry {
        r = call A();
    }
    state Done exit;
    transition S -> Done on success;
}
""",
    "expects 1 argument(s), got 0",
)

expect_error(
    "call argument type mismatch",
    """
workflow W {
    tool T(x: bool) -> bool;
    agent A uses T;
    state S entry {
        n = 5;
        r = call A(n);
    }
    state Done exit;
    transition S -> Done on success;
}
""",
    "expects bool, got number",
)

# ---- assignment consistency ----
expect_error(
    "reassigning a variable with a different type",
    """
workflow W {
    tool T() -> bool;
    agent A uses T;
    state S entry {
        x = 5;
        x = call A();
    }
    state Done exit;
    transition S -> Done on success;
}
""",
    "cannot reassign it as bool",
)

# ---- use-before-assignment / scope isolation ----
expect_error(
    "use before assignment",
    """
workflow W {
    state S entry {
        y = x + 1;
    }
    state Done exit;
    transition S -> Done;
}
""",
    "'x' is used before it is assigned",
)

expect_error(
    "variables do not leak between states",
    """
workflow W {
    state S entry {
        total = 100;
    }
    state Next {
        y = total + 1;
    }
    state Done exit;
    transition S -> Next;
    transition Next -> Done;
}
""",
    "'total' is used before it is assigned",
)

# ---- void handling ----
expect_error(
    "assigning a void call's result",
    """
workflow W {
    tool T() -> void;
    agent A uses T;
    state S entry {
        r = call A();
    }
    state Done exit;
    transition S -> Done;
}
""",
    "returns void",
)

expect_error(
    "discarding a non-void call's result",
    """
workflow W {
    tool T() -> bool;
    agent A uses T;
    state S entry {
        call A();
    }
    state Done exit;
    transition S -> Done;
}
""",
    "is not used; assign it",
)

# ---- string literal handling (new) ----
expect_clean(
    "string literal passed to a string parameter",
    """
workflow W {
    tool SendEmail(to: string) -> void;
    agent Mailer uses SendEmail;
    state S entry {
        call Mailer("hello@example.com");
    }
    state Done exit;
    transition S -> Done;
}
""",
)

expect_error(
    "string literal passed to a number parameter",
    """
workflow W {
    tool Charge(amount: number) -> void;
    agent Payer uses Charge;
    state S entry {
        call Payer("not-a-number");
    }
    state Done exit;
    transition S -> Done;
}
""",
    "expects number, got string",
)

# ---- the real example, still clean ----
example_path = os.path.join(
    os.path.dirname(__file__), "..", "examples", "order_processor.aflow"
)
with open(example_path, "r", encoding="utf-8") as f:
    ORDER_PROCESSOR_SRC = f.read()

expect_clean("the real order_processor.aflow example", ORDER_PROCESSOR_SRC)

print()
print("%d passed, %d failed" % (PASS_COUNT, FAIL_COUNT))
if FAIL_COUNT:
    raise SystemExit(1)
