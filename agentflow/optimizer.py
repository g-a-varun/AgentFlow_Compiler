# agentflow/optimizer.py
#
# Three classical optimizations over the three-address IR:
#
#   1. Constant folding
#         ADD t, 2, 3   ->   ASSIGN t, 5
#      Replaces any arithmetic instruction whose two operands are both
#      numeric literals with a single ASSIGN.
#
#   2. Dead-state elimination
#      Runs a BFS from the entry state over JUMP / BRANCH edges and
#      removes every labelled block that is never reached.
#
#   3. Branch-chain collapsing (peephole)
#      If a state's block is exactly [ENTER X, JUMP Y] -- i.e. it does
#      no work, has no bind, no action, and just forwards control --
#      every jump or branch that targeted X is redirected to Y, and
#      the block is dropped. The entry state is never collapsed.


class Optimizer:
    def __init__(self):
        self.stats = {
            "constant_folds": 0,
            "dead_instructions_removed": 0,
            "dead_labels_removed": 0,
            "branch_chains_collapsed": 0,
        }

    def optimize(self, program):
        """Runs the passes in order and returns the same program object,
        mutated in place. Caller can read .stats for a summary."""
        self._constant_folding(program)
        self._dead_state_elimination(program)
        self._branch_chain_collapsing(program)
        return program

    # ---- helpers ----

    @staticmethod
    def _blocks(program):
        """Returns a list of (label, start_index, end_index) for every
        labelled block, in instruction order. A block runs from the
        label's instruction up to the next label (exclusive)."""
        sorted_labels = sorted(program.labels.items(), key=lambda kv: kv[1])
        blocks = []
        for i, (label, start) in enumerate(sorted_labels):
            if i + 1 < len(sorted_labels):
                end = sorted_labels[i + 1][1]
            else:
                end = len(program.instructions)
            blocks.append((label, start, end))
        return blocks

    # ---- pass 1 ----

    def _constant_folding(self, program):
        for instr in program.instructions:
            if instr.op in ("ADD", "SUB", "MUL", "DIV"):
                _, a, b = instr.args
                try:
                    av = int(a)
                    bv = int(b)
                except (ValueError, TypeError):
                    continue  # at least one operand is not a plain number
                if instr.op == "ADD":
                    result = av + bv
                elif instr.op == "SUB":
                    result = av - bv
                elif instr.op == "MUL":
                    result = av * bv
                else:  # DIV
                    if bv == 0:
                        continue  # leave as-is; interpreter would error anyway
                    result = av // bv
                dst = instr.args[0]
                instr.op = "ASSIGN"
                instr.args = (dst, str(result))
                self.stats["constant_folds"] += 1

    # ---- pass 2 ----

    def _dead_state_elimination(self, program):
        blocks = self._blocks(program)
        block_indices = {label: (start, end) for label, start, end in blocks}

        reachable = set()
        queue = [program.entry]
        while queue:
            label = queue.pop()
            if label in reachable or label not in block_indices:
                continue
            reachable.add(label)
            start, end = block_indices[label]
            for idx in range(start, end):
                instr = program.instructions[idx]
                if instr.op == "JUMP":
                    queue.append(instr.args[0])
                elif instr.op == "BRANCH":
                    _, t, f = instr.args
                    if t is not None:
                        queue.append(t)
                    if f is not None:
                        queue.append(f)

        kept = []
        new_labels = {}
        for label, start, end in blocks:
            if label not in reachable:
                self.stats["dead_labels_removed"] += 1
                continue
            new_labels[label] = len(kept)
            for idx in range(start, end):
                kept.append(program.instructions[idx])

        self.stats["dead_instructions_removed"] = len(program.instructions) - len(kept)
        program.instructions = kept
        program.labels = new_labels

    # ---- pass 3 ----

    def _branch_chain_collapsing(self, program):
        """Repeats until no more collapsing is possible: find every
        non-entry label whose block is exactly [ENTER X, JUMP Y], build
        an alias X -> Y, rewrite every JUMP / BRANCH target through the
        alias, then drop the aliased block."""
        while True:
            blocks = self._blocks(program)
            alias = {}
            for label, start, end in blocks:
                if label == program.entry:
                    continue
                if end - start != 2:
                    continue
                enter_instr = program.instructions[start]
                jump_instr = program.instructions[start + 1]
                if enter_instr.op != "ENTER" or jump_instr.op != "JUMP":
                    continue
                target = jump_instr.args[0]
                if target == label:
                    continue  # self-loop, leave alone
                alias[label] = target

            if not alias:
                break

            def resolve(x):
                seen = set()
                while x in alias and x not in seen:
                    seen.add(x)
                    x = alias[x]
                return x

            for instr in program.instructions:
                if instr.op == "JUMP":
                    old = instr.args[0]
                    new = resolve(old)
                    if new != old:
                        instr.args = (new,)
                elif instr.op == "BRANCH":
                    cond, t, f = instr.args
                    new_t = resolve(t) if t is not None else None
                    new_f = resolve(f) if f is not None else None
                    if new_t != t or new_f != f:
                        instr.args = (cond, new_t, new_f)

            kept = []
            new_labels = {}
            for label, start, end in blocks:
                if label in alias:
                    self.stats["branch_chains_collapsed"] += 1
                    continue
                new_labels[label] = len(kept)
                for idx in range(start, end):
                    kept.append(program.instructions[idx])
            program.instructions = kept
            program.labels = new_labels
