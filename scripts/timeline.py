from enum import Enum
from collections import defaultdict


class Records(object):
    def __init__(self, mask=None, key_func=lambda r: r):
        self.record_starts = {}
        self.record_times = defaultdict(lambda: 0.0)
        self.active = False

        # a function applied to records to determine keys for how the record is stored
        self.key_func = key_func

        # update myself immediately
        if mask:
            self.set_active_mask(mask)
        else:
            self.mask = None

    def notify(self, ts):
        """The mask that we listen for has changed"""
        next_active = self.mask.evaluate()
        if self.active and not next_active:  # active -> inactive
            self.pause_records(ts)
        elif not self.active and next_active:  # inactive -> active
            self.resume_records(ts)
        self.active = next_active

    def start_record(self, ts, record):
        key = self.key_func(record)
        assert key not in self.record_starts
        if self.active:
            self.record_starts[key] = ts  # if we're active, track the time
        else:
            # next time we become active, we'll start tracking the time
            self.record_starts[key] = None

    def end_record(self, ts, record):
        key = self.key_func(record)
        if key in self.record_starts:  # may have already ended this record if it was the cause of the Expr going inactive
            # may have already paused this record
            if self.record_starts[key] is not None:
                self.record_times[key] += ts - self.record_starts[key]
            del self.record_starts[key]

    def pause_records(self, ts):
        """ accumulate time for all records we are tracking"""
        for key in list(self.record_starts.keys()):
            # self.print("pausing", key, "@", ts)
            self.record_times[key] += ts - self.record_starts[key]
            self.record_starts[key] = None

    def resume_records(self, ts):
        """ resume tracking time for all records we are tracking"""
        # when we go active, b
        for key in list(self.record_starts.keys()):
            # self.print("resuming", key, "@", ts)
            # one of these records may have made us go active, so it won't be none
            if self.record_starts[key] is None:
                self.record_starts[key] = ts

    def set_active_mask(self, mask):
        """set which mask controls when these records are active"""
        self.mask = mask
        mask.add_listener(self)
        self.notify(0)


class Operator(Enum):
    OR = 1
    AND = 2
    INV = 3


class Expr(object):
    def __init__(self, lhs, op, rhs):
        assert isinstance(rhs, Expr)
        assert isinstance(op, Operator)
        self.listeners = set()  # objects that need to be notified when I change
        self.lhs = lhs
        self.op = op
        self.rhs = rhs
        self.time = 0.0  # amount of time this has been active
        self.activated_at = None  # when this timeline last became busy, or None if idle
        if op == Operator.INV:
            assert self.lhs is None
            self.evaluate_func = self.inv_eval_func
        elif op == Operator.AND:
            self.evaluate_func = self.and_eval_func
        else:
            self.evaluate_func = self.or_eval_func

        if self.rhs is not None:
            self.rhs.add_listener(self)
        if self.lhs is not None:
            self.lhs.add_listener(self)

        self.verbose = False
        self.name = str(id(self))

        self.record_key = lambda r: r

        # update myself immediately so that my initial value is correct
        # FIXME: may not start at t=0 sometimes
        self.notify(0)

    def inv_eval_func(self):
        return not self.rhs.evaluate()

    def or_eval_func(self):
        return self.lhs.evaluate() or self.rhs.evaluate()

    def and_eval_func(self):
        return self.lhs.evaluate() and self.rhs.evaluate()

    def evaluate(self):
        """we should have already been updated by our children if they changed"""
        return self.activated_at is not None

    def print(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    def notify(self, ts):
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
            changed = True

        elif self.evaluate() and not new_val:  # active to inactive
            # self.print("active -> idle @", ts)
            self.time += ts - self.activated_at
            self.activated_at = None
            changed = True

        # inform parents if I have changed
        if changed:
            self.notify_listeners(ts)

    def notify_listeners(self, ts):
        for l in self.listeners:
            l.notify(ts)

    def add_listener(self, l):
        self.listeners.add(l)

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
        self.listeners = set()
        self.stack = 0

    def set_idle(self, ts):
        assert self.stack >= 0
        self.stack -= 1
        if self.stack == 0:
            self.time += (ts - self.activated_at)
            self.activated_at = None
            self.notify_listeners(ts)

    def set_active(self, ts):
        self.stack += 1
        if self.stack == 1:
            self.activated_at = ts
            self.notify_listeners(ts)

    def __str__(self):
        return str(id(self))


class AlwaysActive(Expr):
    def __init__(self):
        self.listeners = set()

    def evaluate(self):
        return True

    def __str__(self):
        return "1"


class NeverActive(Expr):
    def __init__(self):
        self.listeners = set()

    def evaluate(self):
        return False

    def __str__(self):
        return "0"
