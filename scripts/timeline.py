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
        self.record_starts = {}
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

    def start_record_if_active(self, ts, record):
        if self.evaluate():
            key = self.record_key(record)
            if key in self.record_starts:
                print(record, "already marked as started")
            assert key not in self.record_starts
            self.record_starts[key] = ts

    def end_record(self, ts, record):
        key = self.record_key(record)
        if key in self.record_starts:  # may have already ended this record if it was the cause of the Expr going inactive
            self.record_times[key] += ts - self.record_starts[key]
            del self.record_starts[key]

    def end_all_records(self, ts):
        for key in list(self.record_starts.keys()):
            self.record_times[key] += ts - self.record_starts[key]
            del self.record_starts[key]

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
            # self.print("idle -> busy")
            self.activated_at = ts
            changed = True

        elif self.evaluate() and not new_val:  # active to inactive
            # self.print("busy -> idle")
            self.time += ts - self.activated_at
            self.activated_at = None
            self.end_all_records(ts)
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
            # print("base timeline busy->idle at",
            #       ts, "informing parent", id(p))
            p.child_changed(ts)

    def set_active(self, ts):
        assert self.activated_at is None
        self.activated_at = ts

        for p in self.parents:
            # print("base timeline idle->busy at",
            #       ts, "informing parent", id(p))
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
