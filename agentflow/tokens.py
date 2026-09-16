# agentflow/tokens.py
#
# The Token class: the smallest meaningful unit produced by the lexer.
# Token types are plain strings (not an Enum) because grammar.py uses
# string terminals directly -- "WORKFLOW", "ID", "NUM", "SEMI", etc. --
# and keeping the token type strings identical to those terminal names
# means the parser can look up the ACTION table without any conversion.


class Token:
    def __init__(self, type, value, line, col):
        self.type = type    # token type, e.g. "ID", "NUM", "LBRACE"
        self.value = value  # exact text from source
        self.line = line    # 1-based
        self.col = col      # 1-based

    def __repr__(self):
        return "Token(%s, %r, line=%d, col=%d)" % (
            self.type, self.value, self.line, self.col
        )
