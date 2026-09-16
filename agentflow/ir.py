# agentflow/ir.py
#
# Data structures for the three-address intermediate representation.
#
# An IRProgram is a flat list of Instruction objects plus a label table
# (label name -> instruction index) and the name of the entry state.
#
# Operands in an Instruction are plain strings:
#   - a numeric literal is stored as its text,  e.g. "100"
#   - a string literal is stored with quotes,   e.g. '"hello@example.com"'
#   - a variable or temporary is stored by name, e.g. "total", "t1"
# The interpreter resolves which is which at run time.


class Instruction:
    def __init__(self, op, args=(), line=0, col=0):
        self.op = op  # "ASSIGN" | "ADD" | "SUB" | "MUL" | "DIV"
        # | "CALL" | "JUMP" | "BRANCH" | "ENTER" | "HALT"
        self.args = args  # tuple of operands (strings or, for CALL, nested tuples)
        self.line = line  # source line, for error messages
        self.col = col

    def __repr__(self):
        if self.args:
            return "%s %s" % (self.op, ", ".join(str(a) for a in self.args))
        return self.op


class IRProgram:
    def __init__(self, name):
        self.name = name
        self.instructions = []  # list of Instruction
        self.labels = {}  # label name -> index into instructions
        self.entry = None  # label name of the entry state

    def emit(self, op, args=(), line=0, col=0):
        self.instructions.append(Instruction(op, args, line, col))

    def set_label(self, name):
        """Records that `name` refers to the next instruction to be emitted."""
        self.labels[name] = len(self.instructions)

    def __repr__(self):
        # Show each instruction with any labels that point to it, e.g.:
        #   12  Charge: ENTER Charge
        label_at = {}
        for label, idx in self.labels.items():
            label_at.setdefault(idx, []).append(label)
        lines = []
        for i, instr in enumerate(self.instructions):
            prefix = ""
            if i in label_at:
                prefix = " ".join("%s:" % l for l in label_at[i]) + " "
            lines.append("%3d  %s%s" % (i, prefix, instr))
        return "\n".join(lines)
