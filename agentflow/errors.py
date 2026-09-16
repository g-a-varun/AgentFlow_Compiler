# agentflow/errors.py
#
# Every error type the compiler can raise, in one place. Each one carries
# a message plus the source location (line, col) so that error reporting
# at any stage can point at a real spot in the .aflow file.
#
# LexError  -- raised by lexer.py
# ParseError -- raised by parser.py
# SemanticError -- raised by semantic.py
# IRError -- raised during IR generation / interpretation


class AgentFlowError(Exception):
    """Base class for every AgentFlow compilation error."""

    pass


class LexError(AgentFlowError):
    def __init__(self, message, line, col):
        self.message = message
        self.line = line
        self.col = col
        super().__init__("line %d, col %d: %s" % (line, col, message))


class ParseError(AgentFlowError):
    def __init__(self, message, line, col):
        self.message = message
        self.line = line
        self.col = col
        super().__init__("line %d, col %d: %s" % (line, col, message))


class SemanticError(AgentFlowError):
    def __init__(self, message, line, col):
        self.message = message
        self.line = line
        self.col = col
        super().__init__("line %d, col %d: %s" % (line, col, message))


class IRError(AgentFlowError):
    def __init__(self, message):
        self.message = message
        super().__init__("IRError: %s" % message)
