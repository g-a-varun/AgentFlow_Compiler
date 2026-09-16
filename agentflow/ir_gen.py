# agentflow/ir_gen.py
#
# Lowers the AST (built by parser.py) into a flat three-address IR
# program. Each state becomes a labelled block; transitions become
# BRANCH (on a boolean outcome) or JUMP (unconditional). Exit states
# end in HALT.
#
# Temps are named t1, t2, ... . Every arithmetic subexpression is
# lowered into its own temp, so an expression like
#     fee = 2 + 3
# becomes
#     ADD t1, 2, 3
#     ASSIGN fee, t1
# which is the shape the optimizer will constant-fold later.

from .ir import IRProgram
from .ast_nodes import (
    ProgramNode,
    StateDeclNode,
    TransitionDeclNode,
    BindDeclNode,
    AssignNode,
    AssignCallNode,
    CallNode,
    BinaryExprNode,
    NumberLiteralNode,
    StringLiteralNode,
    IdentifierNode,
)


_BINOP = {"PLUS": "ADD", "MINUS": "SUB", "MUL": "MUL", "DIV": "DIV"}


class IRGenerator:
    def __init__(self):
        self.program = IRProgram("")
        self.temp_counter = 0
        self.transitions_by_from = {}  # state -> list of TransitionDeclNode
        self.bind_by_state = {}  # state -> BindDeclNode

    def _new_temp(self):
        self.temp_counter += 1
        return "t%d" % self.temp_counter

    def generate(self, ast):
        self.program = IRProgram(ast.name)
        self.temp_counter = 0
        self.transitions_by_from = {}
        self.bind_by_state = {}

        # First index transitions and binds, and find the entry state.
        for decl in ast.decls:
            if isinstance(decl, TransitionDeclNode):
                self.transitions_by_from.setdefault(decl.from_state, []).append(decl)
            elif isinstance(decl, BindDeclNode):
                self.bind_by_state[decl.state_name] = decl
            elif isinstance(decl, StateDeclNode) and decl.modifier == "entry":
                self.program.entry = decl.name

        if self.program.entry is None:
            # Semantic analysis should have caught this; raise clearly anyway.
            raise ValueError("no entry state in workflow '%s'" % ast.name)

        # Then generate each state's block, in source order.
        for decl in ast.decls:
            if isinstance(decl, StateDeclNode):
                self._gen_state(decl)

        return self.program

    # ---- per-state block ----

    def _gen_state(self, state):
        self.program.set_label(state.name)
        self.program.emit("ENTER", (state.name,), state.line, state.col)

        # 1. Action block, if any.
        if state.actions:
            for action in state.actions:
                self._gen_action(action)

        # 2. Bind, if any (mutually exclusive with action block by spec).
        bind = self.bind_by_state.get(state.name)
        if bind is not None:
            t = self._new_temp()
            self.program.emit("CALL", (t, bind.agent_name, ()), state.line, state.col)

        # 3. Transitions.
        transitions = self.transitions_by_from.get(state.name, [])
        conditioned = [t for t in transitions if t.condition is not None]
        unconditioned = [t for t in transitions if t.condition is None]

        if conditioned:
            # The outcome variable is either the last action's variable (if
            # the action block ends in an assignment-call) or the bind's temp.
            outcome_var = None
            if bind is not None:
                outcome_var = t  # the temp just emitted above
            elif state.actions and isinstance(state.actions[-1], AssignCallNode):
                outcome_var = state.actions[-1].var_name

            success_target = None
            failure_target = None
            for tr in conditioned:
                if tr.condition == "success":
                    success_target = tr.to_state
                elif tr.condition == "failure":
                    failure_target = tr.to_state
                # Any other condition label is currently treated as "not
                # success and not failure", i.e. it will never be taken.
                # The semantic analyzer only inspects success/failure.

            if outcome_var is None:
                # Semantic analysis should have caught this.
                self.program.emit("HALT", (), state.line, state.col)
            else:
                self.program.emit(
                    "BRANCH",
                    (outcome_var, success_target, failure_target),
                    state.line,
                    state.col,
                )

        elif unconditioned:
            # Take the first unconditioned transition. The spec allows at
            # most one in practice; if there were more, they would be
            # indistinguishable and only the first is meaningful.
            self.program.emit(
                "JUMP", (unconditioned[0].to_state,), state.line, state.col
            )

        else:
            # No outgoing transitions: exit state (semantic guarantees
            # this only happens for states marked exit).
            self.program.emit("HALT", (), state.line, state.col)

    # ---- actions ----

    def _gen_action(self, action):
        if isinstance(action, AssignNode):
            t = self._gen_expr(action.expr)
            self.program.emit("ASSIGN", (action.var_name, t), action.line, action.col)

        elif isinstance(action, AssignCallNode):
            arg_names = [self._gen_expr(a) for a in action.args]
            self.program.emit(
                "CALL",
                (action.var_name, action.agent_name, tuple(arg_names)),
                action.line,
                action.col,
            )

        elif isinstance(action, CallNode):
            arg_names = [self._gen_expr(a) for a in action.args]
            self.program.emit(
                "CALL",
                (None, action.agent_name, tuple(arg_names)),
                action.line,
                action.col,
            )

    # ---- expressions ----

    def _gen_expr(self, expr):
        if isinstance(expr, NumberLiteralNode):
            return str(expr.value)
        if isinstance(expr, StringLiteralNode):
            return '"%s"' % expr.value
        if isinstance(expr, IdentifierNode):
            return expr.name
        if isinstance(expr, BinaryExprNode):
            left = self._gen_expr(expr.left)
            right = self._gen_expr(expr.right)
            t = self._new_temp()
            self.program.emit(_BINOP[expr.op], (t, left, right), expr.line, expr.col)
            return t
        raise ValueError("unknown expression node: %r" % expr)
