# agentflow/__init__.py
#
# AgentFlow compiler package.
#
# Pipeline: lexer -> parser -> semantic -> IR -> optimizer
#           then either interpreter (mocked) or codegen_langgraph (Python).
#
# Run the whole thing with:  python -m agentflow <file.aflow>

__version__ = "0.1.0"
