# agentflow/lexer.py
#
# Turns AgentFlow source text into a list of Token objects.
# Written character by character on purpose (no regex, no lexer
# generator) so every step of tokenizing is visible and easy to
# explain in a viva.
#
# The caller is responsible for reading the .aflow file; this module
# only sees the text. On bad input it raises LexError with the exact
# line and column of the offending character.

from .tokens import Token
from .errors import LexError


# Reserved words. Anything else that looks like an identifier becomes ID.
KEYWORDS = {
    "workflow": "WORKFLOW",
    "tool": "TOOL",
    "agent": "AGENT",
    "state": "STATE",
    "transition": "TRANSITION",
    "bind": "BIND",
    "uses": "USES",
    "on": "ON",
    "entry": "ENTRY",
    "exit": "EXIT",
    "string": "STRING",  # the *type* keyword string
    "number": "NUMBER",  # the *type* keyword number
    "bool": "BOOL",
    "void": "VOID",
    "call": "CALL",
    "if": "IF",  # reserved for the nested-conditional stretch goal
}


# Punctuation and operators that are exactly one character.
SINGLE_CHAR_TOKENS = {
    "{": "LBRACE",
    "}": "RBRACE",
    "(": "LPAREN",
    ")": "RPAREN",
    ",": "COMMA",
    ":": "COLON",
    ";": "SEMI",
    "=": "ASSIGN",
    "+": "PLUS",
    "-": "MINUS",
    "*": "MUL",
    "/": "DIV",
}


def tokenize(source):
    """
    Tokenize AgentFlow source text and return a list of Token objects,
    ending with a single Token("EOF", "", line, col).

    Raises LexError on the first character that cannot start a token.
    """
    tokens = []
    i = 0
    line = 1
    col = 1
    n = len(source)

    while i < n:
        ch = source[i]

        # newline: advance the line, do not emit a token
        if ch == "\n":
            i += 1
            line += 1
            col = 1
            continue

        # other whitespace
        if ch == " " or ch == "\t" or ch == "\r":
            i += 1
            col += 1
            continue

        # line comments: // until end of line
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue

        start_line = line
        start_col = col

        # identifiers and keywords: letter or underscore, then
        # letters/digits/underscores
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            word = source[i:j]
            lower_word = word.lower()
            if lower_word in KEYWORDS:
                token_type = KEYWORDS[lower_word]
            else:
                token_type = "ID"
            tokens.append(Token(token_type, word, start_line, start_col))
            col += j - i
            i = j
            continue

        # numeric literals (integers only for now)
        if ch.isdigit():
            j = i
            while j < n and source[j].isdigit():
                j += 1
            number_text = source[i:j]
            tokens.append(Token("NUM", number_text, start_line, start_col))
            col += j - i
            i = j
            continue

        # string literals: double-quoted, no escape sequences yet,
        # must close on the same line
        if ch == '"':
            j = i + 1
            while j < n and source[j] != '"' and source[j] != "\n":
                j += 1
            if j >= n or source[j] != '"':
                raise LexError("unterminated string literal", start_line, start_col)
            text = source[i + 1 : j]  # contents without the quotes
            tokens.append(Token("STRING_LIT", text, start_line, start_col))
            col += j - i + 1
            i = j + 1
            continue

        # two-character operator: ->
        if ch == "-" and i + 1 < n and source[i + 1] == ">":
            tokens.append(Token("ARROW", "->", start_line, start_col))
            i += 2
            col += 2
            continue

        # one-character tokens
        if ch in SINGLE_CHAR_TOKENS:
            tokens.append(Token(SINGLE_CHAR_TOKENS[ch], ch, start_line, start_col))
            i += 1
            col += 1
            continue

        # nothing matched: this character is not part of the language
        raise LexError("unexpected character %r" % ch, start_line, start_col)

    tokens.append(Token("EOF", "", line, col))
    return tokens
