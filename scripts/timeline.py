from enum import Enum


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
        if op == Operator.INV:
            self.evaluate_func = lambda: not rhs.evaluate()
        elif op == Operator.AND:
            self.evaluate_func = lambda: lhs.evaluate() and rhs.evaluate()
        else:
            self.evaluate_func = lambda: lhs.evaluate() or rhs.evaluate()

        if self.rhs:
            self.rhs.add_parent(self)
        if self.lhs:
            self.lhs.add_parent(self)

    def evaluate(self):
        """ we should have already been updated by our children if they changed"""
        return self.activated_at is not None

    def child_changed(self, ts):
        # print("me:", id(self))
        # print("my child changed")
        # if my child changed, evalute my new state
        new_val = self.evaluate_func()
        # print("i went from", self.activated_at, '->', new_val)

        # if I change, then we need to have our parents update as well
        changed = False
        if new_val and self.activated_at is None:  # inactive to active
            self.activated_at = ts
            changed = True
            # print("idle -> busy")
        elif not new_val and self.activated_at:  # active to inactive
            self.time += ts - self.activated_at
            self.activated_at = None
            changed = True
            # print("busy -> idle")

        # inform parents if I have changed
        if changed:
            for p in self.parents:
                p.child_changed(ts)

    def add_parent(self, parent):
        self.parents.add(parent)

    def operands(self):
        ret = []
        if isinstance(self.lhs, Expr):
            ret += [self.lhs.operands()]
        else:
            ret += [self.lhs]
        if isinstance(self.rhs, Expr):
            ret += [self.rhs.operands()]
        else:
            ret += [self.rhs]
        return ret

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
        self.num_active = 0
        self.time = 0.0
        self.activated_at = None
        self.parents = set()

    def set_idle(self, ts):
        changed = False
        self.num_active -= 1
        assert self.num_active >= 0
        if self.num_active == 0:
            changed = True
            self.time += (ts - self.activated_at)
            self.activated_at = None
        if changed:
            for p in self.parents:
                # print("base timeline busy->idle at",
                #       ts, "informing parent", id(p))
                p.child_changed(ts)

    def set_active(self, ts):
        changed = False
        if self.num_active == 0:
            changed = True
            self.activated_at = ts
        self.num_active += 1

        if changed:
            for p in self.parents:
                # print("base timeline idle->busy at",
                #       ts, "informing parent", id(p))
                p.child_changed(ts)

    def evaluate(self):
        return self.num_active > 0

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
