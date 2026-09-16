# agentflow/semantic.py
#
# Walks the AST built by parser.py and checks it against every rule in
# the language spec. Building the symbol table happens as part of this
# walk rather than as a separate pass, because every tool/agent/state
# has to be known before any state's action block or any transition can
# be checked against it -- so declarations are collected first, then
# everything else is checked against that.

from .errors import SemanticError
from .symbol_table import SymbolTable
from .ast_nodes import (
    ToolDeclNode,
    AgentDeclNode,
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


class SemanticAnalyzer:
    def __init__(self):
        self.symtab = SymbolTable()
        self.errors = []
        self.transitions_by_from = {}  # state name -> list of TransitionDeclNode
        self.bind_by_state = {}  # state name -> BindDeclNode

    def analyze(self, program):
        """
        Runs every check on the given ProgramNode. Returns True if no
        errors were found. self.errors holds every SemanticError found,
        in the order the checks ran -- the analyzer does not stop at
        the first problem, so a single bad workflow can be shown all of
        its mistakes in one run instead of one at a time.
        """
        self._collect_declarations(program)
        self._check_agent_tool_references(program)
        self._index_transitions_and_binds(program)
        self._check_transition_and_bind_targets(program)
        self._check_entry_exit(program)
        self._check_reachability(program)
        self._check_transition_consistency(program)
        self._check_bind_action_exclusivity(program)
        self._check_outcome_resolution(program)
        self._check_action_blocks(program)
        return len(self.errors) == 0

    def _error(self, message, line, col):
        self.errors.append(SemanticError(message, line, col))

    # ---- pass 1: collect every declared tool / agent / state, and
    # catch duplicate names while doing it ----
    def _collect_declarations(self, program):
        for decl in program.decls:
            if isinstance(decl, ToolDeclNode):
                if self.symtab.lookup_tool(decl.name):
                    self._error(
                        "tool '%s' is already declared" % decl.name, decl.line, decl.col
                    )
                else:
                    self.symtab.declare_tool(decl)
                # a tool's parameters must have distinct names
                seen_params = set()
                for param_name, _param_type in decl.params:
                    if param_name in seen_params:
                        self._error(
                            "tool '%s' has a duplicate parameter '%s'"
                            % (decl.name, param_name),
                            decl.line,
                            decl.col,
                        )
                    seen_params.add(param_name)
            elif isinstance(decl, AgentDeclNode):
                if self.symtab.lookup_agent(decl.name):
                    self._error(
                        "agent '%s' is already declared" % decl.name,
                        decl.line,
                        decl.col,
                    )
                else:
                    self.symtab.declare_agent(decl)
            elif isinstance(decl, StateDeclNode):
                if self.symtab.lookup_state(decl.name):
                    self._error(
                        "state '%s' is already declared" % decl.name,
                        decl.line,
                        decl.col,
                    )
                else:
                    self.symtab.declare_state(decl)

    def _check_agent_tool_references(self, program):
        for decl in program.decls:
            if isinstance(decl, AgentDeclNode):
                if self.symtab.lookup_tool(decl.tool_name) is None:
                    self._error(
                        "agent '%s' uses undeclared tool '%s'"
                        % (decl.name, decl.tool_name),
                        decl.line,
                        decl.col,
                    )

    def _index_transitions_and_binds(self, program):
        for decl in program.decls:
            if isinstance(decl, TransitionDeclNode):
                self.transitions_by_from.setdefault(decl.from_state, []).append(decl)
            elif isinstance(decl, BindDeclNode):
                if decl.state_name in self.bind_by_state:
                    self._error(
                        "state '%s' already has a bind" % decl.state_name,
                        decl.line,
                        decl.col,
                    )
                else:
                    self.bind_by_state[decl.state_name] = decl

    def _check_transition_and_bind_targets(self, program):
        for decl in program.decls:
            if isinstance(decl, TransitionDeclNode):
                if self.symtab.lookup_state(decl.from_state) is None:
                    self._error(
                        "transition leaves undeclared state '%s'" % decl.from_state,
                        decl.line,
                        decl.col,
                    )
                if self.symtab.lookup_state(decl.to_state) is None:
                    self._error(
                        "transition enters undeclared state '%s'" % decl.to_state,
                        decl.line,
                        decl.col,
                    )
            elif isinstance(decl, BindDeclNode):
                if self.symtab.lookup_state(decl.state_name) is None:
                    self._error(
                        "bind refers to undeclared state '%s'" % decl.state_name,
                        decl.line,
                        decl.col,
                    )
                if self.symtab.lookup_agent(decl.agent_name) is None:
                    self._error(
                        "bind refers to undeclared agent '%s'" % decl.agent_name,
                        decl.line,
                        decl.col,
                    )

    def _check_entry_exit(self, program):
        entries = [
            d
            for d in program.decls
            if isinstance(d, StateDeclNode) and d.modifier == "entry"
        ]
        exits = [
            d
            for d in program.decls
            if isinstance(d, StateDeclNode) and d.modifier == "exit"
        ]
        if len(entries) == 0:
            self._error("workflow has no entry state", program.line, program.col)
        elif len(entries) > 1:
            for e in entries[1:]:
                self._error(
                    "workflow has more than one entry state ('%s')" % e.name,
                    e.line,
                    e.col,
                )
        if len(exits) == 0:
            self._error("workflow has no exit state", program.line, program.col)

    def _check_reachability(self, program):
        entries = [
            d
            for d in program.decls
            if isinstance(d, StateDeclNode) and d.modifier == "entry"
        ]
        if not entries:
            return  # already reported by _check_entry_exit
        start = entries[0].name

        # BFS over the transition graph, following only edges whose
        # from-state we actually know about
        seen = set([start])
        queue = [start]
        while queue:
            current = queue.pop(0)
            for t in self.transitions_by_from.get(current, []):
                if t.to_state not in seen:
                    seen.add(t.to_state)
                    queue.append(t.to_state)

        for decl in program.decls:
            if isinstance(decl, StateDeclNode) and decl.name not in seen:
                self._error(
                    "state '%s' can never be reached from the entry state" % decl.name,
                    decl.line,
                    decl.col,
                )

        # dead end: a non-exit state with no outgoing transitions at all
        for decl in program.decls:
            if isinstance(decl, StateDeclNode) and decl.modifier != "exit":
                if decl.name not in self.transitions_by_from:
                    self._error(
                        "state '%s' has no outgoing transitions and is not marked exit"
                        % decl.name,
                        decl.line,
                        decl.col,
                    )

    # the two outcome labels a conditioned transition may route on
    VALID_OUTCOMES = ("success", "failure")

    def _check_transition_consistency(self, program):
        """
        Enforces that the transitions leaving each state form an
        unambiguous dispatch, so IR generation never has to silently pick
        one transition and drop the others:

          - at most one unconditioned transition per state;
          - a state does not mix a conditioned transition with an
            unconditioned one;
          - every conditioned transition routes on 'success' or 'failure';
          - no outcome label is used more than once.

        Any of these, left unchecked, produces a workflow whose behaviour
        does not match what was written -- a declared transition that can
        never be taken.
        """
        for state_name, transitions in self.transitions_by_from.items():
            conditioned = [t for t in transitions if t.condition is not None]
            unconditioned = [t for t in transitions if t.condition is None]

            if conditioned and unconditioned:
                for u in unconditioned:
                    self._error(
                        "state '%s' mixes a conditioned transition with an "
                        "unconditioned one; use either 'on success'/'on failure' "
                        "outcomes or a single plain transition, not both"
                        % state_name,
                        u.line,
                        u.col,
                    )
            elif len(unconditioned) > 1:
                for extra in unconditioned[1:]:
                    self._error(
                        "state '%s' has more than one unconditioned transition; "
                        "only one is allowed" % state_name,
                        extra.line,
                        extra.col,
                    )

            seen_labels = set()
            for t in conditioned:
                if t.condition not in self.VALID_OUTCOMES:
                    self._error(
                        "state '%s' has a transition on unknown outcome '%s'; "
                        "only 'success' and 'failure' are allowed"
                        % (state_name, t.condition),
                        t.line,
                        t.col,
                    )
                elif t.condition in seen_labels:
                    self._error(
                        "state '%s' has more than one transition on '%s'; "
                        "each outcome may be used at most once"
                        % (state_name, t.condition),
                        t.line,
                        t.col,
                    )
                else:
                    seen_labels.add(t.condition)

    def _check_bind_action_exclusivity(self, program):
        for decl in program.decls:
            if isinstance(decl, StateDeclNode):
                has_bind = decl.name in self.bind_by_state
                has_actions = decl.actions is not None and len(decl.actions) > 0
                if has_bind and has_actions:
                    self._error(
                        "state '%s' has both a bind and an action block; it can only have one"
                        % decl.name,
                        decl.line,
                        decl.col,
                    )

    def _state_needs_outcome(self, state_name):
        transitions = self.transitions_by_from.get(state_name, [])
        return any(t.condition is not None for t in transitions)

    def _check_outcome_resolution(self, program):
        for decl in program.decls:
            if not isinstance(decl, StateDeclNode):
                continue
            if not self._state_needs_outcome(decl.name):
                continue  # no conditioned outgoing transition, nothing required

            bind = self.bind_by_state.get(decl.name)
            if bind is not None:
                agent = self.symtab.lookup_agent(bind.agent_name)
                tool = self.symtab.lookup_tool(agent.tool_name) if agent else None
                if tool is not None and tool.return_type != "bool":
                    self._error(
                        "state '%s' has a conditioned transition but its bound agent's tool "
                        "returns %s, not bool" % (decl.name, tool.return_type),
                        decl.line,
                        decl.col,
                    )
                continue

            if decl.actions:
                last = decl.actions[-1]
                if isinstance(last, AssignCallNode):
                    agent = self.symtab.lookup_agent(last.agent_name)
                    tool = self.symtab.lookup_tool(agent.tool_name) if agent else None
                    if tool is not None and tool.return_type == "bool":
                        continue  # resolved
                    if tool is not None:
                        self._error(
                            "state '%s' has a conditioned transition but its last call "
                            "returns %s, not bool" % (decl.name, tool.return_type),
                            decl.line,
                            decl.col,
                        )
                        continue
                self._error(
                    "state '%s' has a conditioned transition but its action block does "
                    "not end with a bool-returning call" % decl.name,
                    decl.line,
                    decl.col,
                )
                continue

            self._error(
                "state '%s' has a conditioned transition but no bind and no action block "
                "to resolve it" % decl.name,
                decl.line,
                decl.col,
            )

    # ---- expression type inference, used while checking action blocks ----
    def _infer_expr_type(self, expr):
        if isinstance(expr, NumberLiteralNode):
            return "number"
        if isinstance(expr, StringLiteralNode):
            return "string"
        if isinstance(expr, IdentifierNode):
            t = self.symtab.lookup_local(expr.name)
            if t is None:
                self._error(
                    "'%s' is used before it is assigned" % expr.name,
                    expr.line,
                    expr.col,
                )
                return None
            return t
        if isinstance(expr, BinaryExprNode):
            left_t = self._infer_expr_type(expr.left)
            right_t = self._infer_expr_type(expr.right)
            if left_t is not None and left_t != "number":
                self._error(
                    "arithmetic needs a number, got %s" % left_t,
                    expr.left.line,
                    expr.left.col,
                )
            if right_t is not None and right_t != "number":
                self._error(
                    "arithmetic needs a number, got %s" % right_t,
                    expr.right.line,
                    expr.right.col,
                )
            return "number"
        return None

    def _check_call(self, agent_name, args, line, col):
        """
        Checks a call's arity and argument types against the agent's
        tool signature, and returns the tool's return type (or None if
        the agent/tool could not be resolved -- already reported
        elsewhere in that case).
        """
        agent = self.symtab.lookup_agent(agent_name)
        if agent is None:
            self._error("'%s' is not a declared agent" % agent_name, line, col)
            return None
        tool = self.symtab.lookup_tool(agent.tool_name)
        if tool is None:
            return None  # already reported when agent declarations were checked

        if len(args) != len(tool.params):
            self._error(
                "'%s' expects %d argument(s), got %d"
                % (agent_name, len(tool.params), len(args)),
                line,
                col,
            )
        else:
            for arg_expr, (param_name, param_type) in zip(args, tool.params):
                arg_type = self._infer_expr_type(arg_expr)
                if arg_type is not None and arg_type != param_type:
                    self._error(
                        "argument '%s' expects %s, got %s"
                        % (param_name, param_type, arg_type),
                        arg_expr.line,
                        arg_expr.col,
                    )
        return tool.return_type

    def _declare_or_check_reassignment(self, var_name, new_type, line, col):
        if new_type is None:
            return
        existing_type = self.symtab.lookup_local(var_name)
        if existing_type is not None and existing_type != new_type:
            self._error(
                "'%s' was first used as %s, cannot reassign it as %s"
                % (var_name, existing_type, new_type),
                line,
                col,
            )
        else:
            self.symtab.declare_local(var_name, new_type)

    def _check_action_blocks(self, program):
        for decl in program.decls:
            if not isinstance(decl, StateDeclNode) or decl.actions is None:
                continue
            self.symtab.enter_state_scope()
            for action in decl.actions:
                if isinstance(action, AssignNode):
                    expr_type = self._infer_expr_type(action.expr)
                    self._declare_or_check_reassignment(
                        action.var_name, expr_type, action.line, action.col
                    )

                elif isinstance(action, AssignCallNode):
                    ret_type = self._check_call(
                        action.agent_name, action.args, action.line, action.col
                    )
                    if ret_type == "void":
                        self._error(
                            "cannot assign the result of '%s', which returns void"
                            % action.agent_name,
                            action.line,
                            action.col,
                        )
                    else:
                        self._declare_or_check_reassignment(
                            action.var_name, ret_type, action.line, action.col
                        )

                elif isinstance(action, CallNode):
                    ret_type = self._check_call(
                        action.agent_name, action.args, action.line, action.col
                    )
                    if ret_type is not None and ret_type != "void":
                        self._error(
                            "the result of calling '%s' is not used; assign it to a variable"
                            % action.agent_name,
                            action.line,
                            action.col,
                        )
