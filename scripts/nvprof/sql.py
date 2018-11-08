class Expr(object):
    def __init__(self, s):
        self.s = s

    def __str__(self, s):
        return str(self.s)


class ResultColumn(object):
    def __init__(self, expr=None, table_name=None):
        self.expr = expr
        self.table_name = table_name

    def __str__(self):
        if self.expr:
            return str(self.expr)
        elif self.table_name:
            return str(self.table_name)
        else:
            return "*"


class Select(object):
    def __init__(
        self,
        table_or_subquery,
        result_columns=[],
        where_expr=None,
        ordering_terms=[],
        distinct=False,
        all=False,
    ):
        self.table_or_subquery = table_or_subquery
        self.result_columns = result_columns
        self.where_expr = where_expr
        self.ordering_terms = ordering_terms
        self.distinct = distinct
        self.all = all

    def __str__(self):
        if not self.result_columns:
            result_columns = [ResultColumn()]
        else:
            result_columns = self.result_columns
        sql = "SELECT"
        if self.distinct:
            sql += " DISTINCT"
        if self.all:
            sql += " ALL"
        sql += " " + ",".join(str(r) for r in result_columns)
        sql += " FROM " + str(self.table_or_subquery)
        if self.ordering_terms:
            sql += " ORDER BY " + ",".join(str(o) for o in self.ordering_terms)
        return sql

    def ResultColumn(self, *args, **kwargs):
        self.result_columns = list(
            self.result_columns) + [ResultColumn(*args, **kwargs)]
        return self

    def Where(self, *args, **kwargs):
        self.where_expr = Expr(*args, **kwargs)
        return self
