from enum import Enum


class Operator(Enum):
    OR = 1
    AND = 2
    INV = 3


class Expr(object):
    def __init__(self, lhs, op, rhs):
        assert isinstance(rhs, Expr)
        assert isinstance(op, Operator)
        self.lhs = lhs
        self.op = op
        self.rhs = rhs
        self.time = 0.0  # amount of time this has been active
        self.activated_at = None  # when this timeline last became busy, or None if idle
        if op == Operator.INV:
            self.is_active = lambda: not rhs.is_active()
        elif op == Operator.AND:
            self.is_active = lambda: lhs.is_active() and rhs.is_active()
        else:
            self.is_active = lambda: lhs.is_active() or rhs.is_active()

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

    def update(self, ts):
        """update the internal records of this Timeline"""
        next_state = self.is_active()
        if next_state and self.activated_at is None:  # inactive to active
            self.activated_at = ts
        elif not next_state and self.activated_at:  # active to inactive
            self.time += ts - self.activated_at
            self.activated_at = None
        return next_state

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

    def set_idle(self, ts):
        self.num_active -= 1
        assert self.num_active >= 0
        if self.num_active == 0:
            self.time += (ts - self.activated_at)
            self.activated_at = None

    def set_active(self, ts):
        if self.num_active == 0:
            self.activated_at = ts
        self.num_active += 1

    def is_active(self):
        return self.num_active > 0

    def __str__(self):
        return str(id(self))


class AlwaysActive(Expr):
    def __init__(self):
        pass

    def is_active(self):
        return True

    def __str__(self):
        return "1"


class NeverActive(Expr):
    def __init__(self):
        pass

    def is_active(self):
        return False

    def __str__(self):
        return "0"
