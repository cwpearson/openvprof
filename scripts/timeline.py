from enum import Enum
from collections import defaultdict


class Operator(Enum):
    OR = 1
    AND = 2
    INV = 3


class Expr(object):
    def __init__(self, lhs, op, rhs):
        assert isinstance(rhs, Expr)
        assert isinstance(op, Operator)
        self.parents = set()
        self.lhs = lhs
        self.op = op
        self.rhs = rhs
        self.time = 0.0  # amount of time this has been active
        self.activated_at = None  # when this timeline last became busy, or None if idle
        # the start time of all records when they became active
        self.record_starts = {}
        # accumulated time of all records, past and present
        self.record_times = defaultdict(lambda: 0.0)
        if op == Operator.INV:
            assert self.lhs is None
            # self.evaluate_func = lambda: not self.rhs.evaluate()
            self.evaluate_func = self.inv_eval_func
        elif op == Operator.AND:
            self.evaluate_func = self.and_eval_func
        else:
            self.evaluate_func = self.or_eval_func

        if self.rhs is not None:
            self.rhs.add_parent(self)
        if self.lhs is not None:
            self.lhs.add_parent(self)

        self.verbose = False
        self.name = str(id(self))

        self.record_key = lambda r: r

        # update myself immediately so my initial value is correct
        self.child_changed(0)

    def inv_eval_func(self):
        return not self.rhs.evaluate()

    def or_eval_func(self):
        return self.lhs.evaluate() or self.rhs.evaluate()

    def and_eval_func(self):
        return self.lhs.evaluate() and self.rhs.evaluate()

    def start_record(self, ts, record):
        key = self.record_key(record)
        assert key not in self.record_starts
        if self.evaluate():
            self.record_starts[key] = ts  # if we're active, track the time
        else:
            # next time we become active, we'll start tracking the time
            self.record_starts[key] = None

    def end_record(self, ts, record):
        key = self.record_key(record)
        if key in self.record_starts:  # may have already ended this record if it was the cause of the Expr going inactive
            # may have already paused this record
            if self.record_starts[key] is not None:
                self.record_times[key] += ts - self.record_starts[key]
            del self.record_starts[key]

    def pause_all_records(self, ts):
        """ accumulate time for all records we are tracking"""
        for key in list(self.record_starts.keys()):
            # self.print("pausing", key, "@", ts)
            self.record_times[key] += ts - self.record_starts[key]
            self.record_starts[key] = None

    def resume_all_records(self, ts):
        """ resume tracking time for all records we are tracking"""
        # when we go active, b
        for key in list(self.record_starts.keys()):
            # self.print("resuming", key, "@", ts)
            # one of these records may have made us go active, so it won't be none
            if self.record_starts[key] is None:
                self.record_starts[key] = ts

    def evaluate(self):
        """we should have already been updated by our children if they changed"""
        return self.activated_at is not None

    def print(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    def child_changed(self, ts):
        # self.print("child of", self.name, "changed")
        # if my child changed, evalute my new state
        # if self.lhs:
            # self.print("my lhs:", self.lhs.evaluate())
        # self.print("my rhs:", self.rhs.evaluate())
        new_val = self.evaluate_func()

        # if I change, then we need to have our parents update as well
        changed = False
        if not self.evaluate() and new_val:  # inactive to active
            # self.print("idle -> active @", ts)
            self.activated_at = ts
            self.resume_all_records(ts)
            changed = True

        elif self.evaluate() and not new_val:  # active to inactive
            # self.print("active -> idle @", ts)
            self.time += ts - self.activated_at
            self.activated_at = None
            self.pause_all_records(ts)
            changed = True

        # inform parents if I have changed
        if changed:
            for p in self.parents:
                p.child_changed(ts)

    def add_parent(self, parent):
        self.parents.add(parent)

    def __or__(self, other):
        return Expr(self, Operator.OR, other)

    def __and__(self, other):
        return Expr(self, Operator.AND, other)

    def __invert__(self):
        return Expr(None, Operator.INV, self)

    def __str__(self):
        if self.op == Operator.INV:
            return "(!" + str(self.rhs) + ")"
        elif self.op == Operator.AND:
            return "(" + str(self.lhs) + " & " + str(self.rhs) + ")"
        else:
            return "(" + str(self.lhs) + " | " + str(self.rhs) + ")"


class Timeline(Expr):

    def __init__(self):
        self.time = 0.0
        self.activated_at = None
        self.parents = set()

    def set_idle(self, ts):
        assert self.activated_at is not None
        self.time += (ts - self.activated_at)
        self.activated_at = None
        for p in self.parents:
            p.child_changed(ts)

    def set_active(self, ts):
        assert self.activated_at is None
        self.activated_at = ts

        for p in self.parents:
            p.child_changed(ts)

    def evaluate(self):
        return self.activated_at is not None

    def __str__(self):
        return str(id(self))


class AlwaysActive(Expr):
    def __init__(self):
        self.parents = set()

    def evaluate(self):
        return True

    def __str__(self):
        return "1"


class NeverActive(Expr):
    def __init__(self):
        self.parents = set()

    def evaluate(self):
        return False

    def __str__(self):
        return "0"
