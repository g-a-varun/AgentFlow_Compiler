# agentflow/interpreter.py
#
# Executes an IRProgram directly, with mocked agent calls. This is the
# second backend: instead of generating LangGraph Python, we just run
# the IR. Because the agent calls are mocked, the whole thing runs
# offline with no API keys.
#
# Mock agents are given as a dict: agent_name -> callable(args) -> result.
# args is a Python list of already-resolved values (ints, strings, or
# bools). The callable should return whatever the agent's tool returns:
# bool for tools that route on success/failure, None for void tools.

from .errors import IRError


class Interpreter:
    def __init__(self, mock_agents=None):
        self.mock_agents = mock_agents or {}
        self.trace = []

    def run(self, program, verbose=False):
        """
        Runs `program` starting at its entry label. Returns the final
        variable table (a dict). If verbose=True, self.trace contains a
        list of human-readable lines describing each step.
        """
        self.trace = []
        vars = {}
        pc = program.labels[program.entry]
        steps = 0
        max_steps = 100000

        while 0 <= pc < len(program.instructions):
            steps += 1
            if steps > max_steps:
                raise IRError(
                    "execution exceeded %d steps; possible infinite loop" % max_steps
                )

            instr = program.instructions[pc]

            if verbose:
                self.trace.append("pc=%3d  %s" % (pc, instr))

            if instr.op == "ENTER":
                pc += 1

            elif instr.op == "ASSIGN":
                dst, src = instr.args
                vars[dst] = self._resolve(src, vars)
                pc += 1

            elif instr.op in ("ADD", "SUB", "MUL", "DIV"):
                dst, a, b = instr.args
                av = self._resolve(a, vars)
                bv = self._resolve(b, vars)
                if instr.op == "ADD":
                    vars[dst] = av + bv
                elif instr.op == "SUB":
                    vars[dst] = av - bv
                elif instr.op == "MUL":
                    vars[dst] = av * bv
                elif instr.op == "DIV":
                    if bv == 0:
                        raise IRError("division by zero")
                    vars[dst] = av // bv
                pc += 1

            elif instr.op == "CALL":
                dst, agent_name, arg_names = instr.args
                arg_values = [self._resolve(a, vars) for a in arg_names]
                result = self._call_agent(agent_name, arg_values)
                if verbose:
                    pretty = ", ".join(repr(v) for v in arg_values)
                    self.trace.append(
                        "      -> %s(%s) = %r" % (agent_name, pretty, result)
                    )
                if dst is not None:
                    vars[dst] = result
                pc += 1

            elif instr.op == "JUMP":
                (target,) = instr.args
                if verbose:
                    self.trace.append("      -> jump to %s" % target)
                pc = program.labels[target]

            elif instr.op == "BRANCH":
                cond_var, true_target, false_target = instr.args
                cond_value = self._resolve(cond_var, vars)
                if verbose:
                    self.trace.append(
                        "      -> branch on %s=%r" % (cond_var, cond_value)
                    )
                target = true_target if cond_value else false_target
                if target is None:
                    # No transition defined on this outcome; treat as halt.
                    if verbose:
                        self.trace.append("      -> no target, halting")
                    break
                pc = program.labels[target]

            elif instr.op == "HALT":
                if verbose:
                    self.trace.append("      -> halt")
                break

            else:
                raise IRError("unknown opcode %r" % instr.op)

        return vars

    # ---- operand resolution ----

    def _resolve(self, operand, vars):
        """
        Decide what an operand means at run time:
          - if it is an integer already (defensive), return it
          - if it parses as an int, it is a numeric literal
          - if it is a double-quoted string, it is a string literal
          - otherwise it must be a variable name; look it up in `vars`
        """
        if isinstance(operand, (int, bool)):
            return operand
        s = str(operand)

        # Numeric literal?
        try:
            return int(s)
        except ValueError:
            pass

        # String literal?
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]

        # Variable?
        if s in vars:
            return vars[s]

        raise IRError("undefined variable %r at run time" % s)

    def _call_agent(self, agent_name, args):
        try:
            impl = self.mock_agents[agent_name]
        except KeyError:
            raise IRError("no mock implementation for agent %r" % agent_name)
        return impl(args)
