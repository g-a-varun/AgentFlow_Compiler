# agentflow/parser.py
#
# Table-driven SLR parser. It reads the ACTION/GOTO table built in
# grammar.py and the token list produced by lexer.py, and drives the
# standard shift-reduce loop: look at the current state and the next
# token, shift if the table says shift, reduce if it says reduce, and
# stop when it says accept.
#
# The AST is built as a side effect of reducing. Every time a rule is
# reduced, reduce_production() below is called with the values already
# built for the symbols on that rule's right-hand side, and it returns
# whatever value the left-hand side symbol should carry -- usually a new
# AST node, but sometimes just a plain Python list, string, or None
# (there is no AST node for something like "the empty parameter list",
# it is just represented as []).

from . import grammar
from .errors import ParseError
from .ast_nodes import (
    ProgramNode,
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


def reduce_production(pi, children):
    """
    Builds the value for grammar.productions[pi], given the list of
    values already popped for its right-hand side (in left-to-right
    order). For a terminal symbol the value is the Token itself; for a
    nonterminal it is whatever an earlier call to this function already
    returned for it.
    """
    lhs, rhs = grammar.productions[pi]

    if lhs == "Program'":
        # augmented start rule: just forward the Program node
        return children[0]

    if lhs == "Program":
        tok_workflow, tok_id, tok_lbrace, decls, tok_rbrace = children
        return ProgramNode(tok_id.value, decls, tok_workflow.line, tok_workflow.col)

    if lhs == "DeclList":
        if len(rhs) == 2:
            existing, decl = children
            return existing + [decl]
        (decl,) = children
        return [decl]

    if lhs == "Decl":
        # Decl -> ToolDecl | AgentDecl | StateDecl | TransitionDecl | BindDecl
        return children[0]

    if lhs == "ToolDecl":
        (
            tok_tool,
            tok_id,
            tok_lparen,
            params,
            tok_rparen,
            tok_arrow,
            ret_type,
            tok_semi,
        ) = children
        return ToolDeclNode(tok_id.value, params, ret_type, tok_tool.line, tok_tool.col)

    if lhs == "ParamListOpt":
        if len(rhs) == 1:
            return children[0]
        return []

    if lhs == "ParamList":
        if len(rhs) == 3:
            existing, tok_comma, param = children
            return existing + [param]
        (param,) = children
        return [param]

    if lhs == "Param":
        tok_id, tok_colon, type_name = children
        return (tok_id.value, type_name)

    if lhs == "Type":
        # the token's own text is already the right type name: "string"
        # lexes to a token whose .value is "string", same for number,
        # bool, void
        return children[0].value

    if lhs == "AgentDecl":
        tok_agent, tok_id1, tok_uses, tok_id2, tok_semi = children
        return AgentDeclNode(
            tok_id1.value, tok_id2.value, tok_agent.line, tok_agent.col
        )

    if lhs == "StateDecl":
        if len(rhs) == 4:
            tok_state, tok_id, modifier, tok_semi = children
            return StateDeclNode(
                tok_id.value, modifier, None, tok_state.line, tok_state.col
            )
        tok_state, tok_id, modifier, tok_lbrace, actions, tok_rbrace = children
        return StateDeclNode(
            tok_id.value, modifier, actions, tok_state.line, tok_state.col
        )

    if lhs == "StateModOpt":
        if len(rhs) == 0:
            return None
        tok = children[0]
        return tok.type.lower()  # "ENTRY" -> "entry", "EXIT" -> "exit"

    if lhs == "ActionList":
        if len(rhs) == 2:
            existing, action = children
            return existing + [action]
        (action,) = children
        return [action]

    if lhs == "Action":
        if len(rhs) == 4:
            tok_id, tok_assign, expr, tok_semi = children
            return AssignNode(tok_id.value, expr, tok_id.line, tok_id.col)
        if len(rhs) == 8:
            (
                tok_id1,
                tok_assign,
                tok_call,
                tok_id2,
                tok_lparen,
                args,
                tok_rparen,
                tok_semi,
            ) = children
            return AssignCallNode(
                tok_id1.value, tok_id2.value, args, tok_id1.line, tok_id1.col
            )
        tok_call, tok_id, tok_lparen, args, tok_rparen, tok_semi = children
        return CallNode(tok_id.value, args, tok_call.line, tok_call.col)

    if lhs == "ArgListOpt":
        if len(rhs) == 1:
            return children[0]
        return []

    if lhs == "ArgList":
        if len(rhs) == 3:
            existing, tok_comma, expr = children
            return existing + [expr]
        (expr,) = children
        return [expr]

    if lhs == "Expr":
        if len(rhs) == 1:
            return children[0]
        left, tok_op, right = children
        op = "PLUS" if tok_op.type == "PLUS" else "MINUS"
        return BinaryExprNode(op, left, right, left.line, left.col)

    if lhs == "Term":
        if len(rhs) == 1:
            return children[0]
        left, tok_op, right = children
        op = "MUL" if tok_op.type == "MUL" else "DIV"
        return BinaryExprNode(op, left, right, left.line, left.col)

    if lhs == "Factor":
        if len(rhs) == 1:
            tok = children[0]
            if tok.type == "NUM":
                return NumberLiteralNode(int(tok.value), tok.line, tok.col)
            if tok.type == "STRING_LIT":
                return StringLiteralNode(tok.value, tok.line, tok.col)
            return IdentifierNode(tok.value, tok.line, tok.col)
        # Factor -> LPAREN Expr RPAREN
        tok_lparen, expr, tok_rparen = children
        return expr

    if lhs == "TransitionDecl":
        tok_transition, tok_id1, tok_arrow, tok_id2, cond, tok_semi = children
        return TransitionDeclNode(
            tok_id1.value, tok_id2.value, cond, tok_transition.line, tok_transition.col
        )

    if lhs == "TransCondOpt":
        if len(rhs) == 0:
            return None
        tok_on, tok_id = children
        return tok_id.value

    if lhs == "BindDecl":
        tok_bind, tok_id1, tok_colon, tok_id2, tok_semi = children
        return BindDeclNode(tok_id1.value, tok_id2.value, tok_bind.line, tok_bind.col)

    raise ParseError("no reduce rule written for %s -> %s" % (lhs, rhs), 0, 0)


def parse(tokens):
    """
    Runs the SLR parser over a token list from lexer.tokenize() and
    returns the root ProgramNode. Raises ParseError on the first token
    that does not fit the grammar.
    """
    state_stack = [0]
    value_stack = []
    pos = 0

    while True:
        state = state_stack[-1]
        tok = tokens[pos]
        lookahead = grammar.EOF if tok.type == "EOF" else tok.type

        act = grammar.action.get((state, lookahead))

        if act is None:
            raise ParseError(
                "unexpected %s ('%s')" % (tok.type, tok.value),
                tok.line,
                tok.col,
            )

        if act[0] == "shift":
            value_stack.append(tok)
            state_stack.append(act[1])
            pos += 1

        elif act[0] == "reduce":
            pi = act[1]
            lhs, rhs = grammar.productions[pi]
            n = len(rhs)
            if n > 0:
                children = value_stack[-n:]
                del value_stack[-n:]
                del state_stack[-n:]
            else:
                children = []

            new_value = reduce_production(pi, children)
            value_stack.append(new_value)

            top_state = state_stack[-1]
            goto_state = grammar.goto_table.get((top_state, lhs))
            if goto_state is None:
                raise ParseError(
                    "internal error: no GOTO from state %d on %s" % (top_state, lhs),
                    tok.line,
                    tok.col,
                )
            state_stack.append(goto_state)

        elif act[0] == "accept":
            return value_stack[0]

        else:
            raise ParseError(
                "internal error: unknown action %r" % (act,), tok.line, tok.col
            )


def describe(program, indent=0):
    """Prints a readable summary of a parsed ProgramNode."""
    pad = "  " * indent
    print("%sworkflow %s" % (pad, program.name))
    for decl in program.decls:
        cls = decl.__class__.__name__
        if cls == "ToolDeclNode":
            params = ", ".join("%s: %s" % p for p in decl.params)
            print("%s  tool %s(%s) -> %s" % (pad, decl.name, params, decl.return_type))
        elif cls == "AgentDeclNode":
            print("%s  agent %s uses %s" % (pad, decl.name, decl.tool_name))
        elif cls == "StateDeclNode":
            tag = " [%s]" % decl.modifier if decl.modifier else ""
            if decl.actions is None:
                print("%s  state %s%s (no action block)" % (pad, decl.name, tag))
            else:
                print("%s  state %s%s {" % (pad, decl.name, tag))
                for action in decl.actions:
                    acls = action.__class__.__name__
                    if acls == "AssignNode":
                        print("%s      %s = <expr>" % (pad, action.var_name))
                    elif acls == "AssignCallNode":
                        print(
                            "%s      %s = call %s(%d arg(s))"
                            % (
                                pad,
                                action.var_name,
                                action.agent_name,
                                len(action.args),
                            )
                        )
                    elif acls == "CallNode":
                        print(
                            "%s      call %s(%d arg(s))"
                            % (pad, action.agent_name, len(action.args))
                        )
                print("%s  }" % pad)
        elif cls == "TransitionDeclNode":
            cond = " on %s" % decl.condition if decl.condition else ""
            print(
                "%s  transition %s -> %s%s"
                % (pad, decl.from_state, decl.to_state, cond)
            )
        elif cls == "BindDeclNode":
            print("%s  bind %s : %s" % (pad, decl.state_name, decl.agent_name))
