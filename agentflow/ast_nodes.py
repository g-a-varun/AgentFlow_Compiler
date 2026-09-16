# agentflow/ast_nodes.py
#
# One class per kind of thing that can appear in an AgentFlow program.
# These are plain data holders -- no behaviour, just fields -- built by
# parser.py while it reduces the token stream, and later read by
# semantic.py, ir_gen.py, and codegen_langgraph.py. Every node keeps the
# line/col of the token it started at, so later error messages can point
# at real source locations instead of just naming the problem.


# ---- top level ----


class ProgramNode:
    def __init__(self, name, decls, line, col):
        self.name = name  # workflow name, e.g. "OrderProcessor"
        self.decls = decls  # list of Tool/Agent/State/Transition/Bind decls,
        # in source order
        self.line = line
        self.col = col


# ---- declarations ----


class ToolDeclNode:
    def __init__(self, name, params, return_type, line, col):
        self.name = name
        self.params = params  # list of (param_name, type_name) pairs
        self.return_type = return_type  # "string" | "number" | "bool" | "void"
        self.line = line
        self.col = col


class AgentDeclNode:
    def __init__(self, name, tool_name, line, col):
        self.name = name
        self.tool_name = tool_name  # the tool this agent uses
        self.line = line
        self.col = col


class StateDeclNode:
    def __init__(self, name, modifier, actions, line, col):
        self.name = name
        self.modifier = modifier  # None | "entry" | "exit"
        self.actions = actions  # None (no action block) or a list of
        # AssignNode / AssignCallNode / CallNode
        self.line = line
        self.col = col


class TransitionDeclNode:
    def __init__(self, from_state, to_state, condition, line, col):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition  # None or a label string like "success"
        self.line = line
        self.col = col


class BindDeclNode:
    def __init__(self, state_name, agent_name, line, col):
        self.state_name = state_name
        self.agent_name = agent_name
        self.line = line
        self.col = col


# ---- action-block statements ----


class AssignNode:
    """x = <expr> ;"""

    def __init__(self, var_name, expr, line, col):
        self.var_name = var_name
        self.expr = expr
        self.line = line
        self.col = col


class AssignCallNode:
    """x = call SomeAgent(arg1, arg2) ;"""

    def __init__(self, var_name, agent_name, args, line, col):
        self.var_name = var_name
        self.agent_name = agent_name
        self.args = args  # list of expression nodes
        self.line = line
        self.col = col


class CallNode:
    """call SomeAgent(arg1, arg2) ;   (result not assigned)"""

    def __init__(self, agent_name, args, line, col):
        self.agent_name = agent_name
        self.args = args
        self.line = line
        self.col = col


# ---- expressions ----


class BinaryExprNode:
    def __init__(self, op, left, right, line, col):
        self.op = op  # "PLUS" | "MINUS" | "MUL" | "DIV"
        self.left = left
        self.right = right
        self.line = line
        self.col = col


class NumberLiteralNode:
    def __init__(self, value, line, col):
        self.value = value  # int
        self.line = line
        self.col = col


class StringLiteralNode:
    def __init__(self, value, line, col):
        self.value = value  # str, without the surrounding quotes
        self.line = line
        self.col = col


class IdentifierNode:
    def __init__(self, name, line, col):
        self.name = name
        self.line = line
        self.col = col
