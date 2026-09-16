# agentflow/symbol_table.py
#
# Two-tier symbol table. The global tier holds every tool, agent, and
# state declared at the top level of the workflow -- these all have to
# be known before any state's action block or any transition can be
# checked against them, so they get collected in one pass first.
#
# The local tier holds the variables assigned inside one state's action
# block. It is a single dict, not a stack of scopes, because action
# blocks do not nest (there is no if/while inside one yet). Call
# enter_state_scope() before checking each state so the previous
# state's variables do not leak into the next one.


class SymbolTable:
    def __init__(self):
        self.tools = {}  # name -> ToolDeclNode
        self.agents = {}  # name -> AgentDeclNode
        self.states = {}  # name -> StateDeclNode
        self.local = {}  # name -> "number" | "bool" | "string" | "void"

    def enter_state_scope(self):
        self.local = {}

    def declare_tool(self, node):
        self.tools[node.name] = node

    def declare_agent(self, node):
        self.agents[node.name] = node

    def declare_state(self, node):
        self.states[node.name] = node

    def lookup_tool(self, name):
        return self.tools.get(name)

    def lookup_agent(self, name):
        return self.agents.get(name)

    def lookup_state(self, name):
        return self.states.get(name)

    def declare_local(self, name, type_name):
        self.local[name] = type_name

    def lookup_local(self, name):
        return self.local.get(name)
