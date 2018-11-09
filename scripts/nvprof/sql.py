"""

Get edges from sqlite

select * from
(
select _id_ as id,
          start as ts,
		  'pos' as edge,
		  'CUPTI_ACTIVITY_KIND_RUNTIME' as [table_name]
from CUPTI_ACTIVITY_KIND_RUNTIME
union all
select _id_, end, 'neg', 'CUPTI_ACTIVITY_KIND_RUNTIME' from CUPTI_ACTIVITY_KIND_RUNTIME
union all
select _id_ as id, end as ts, 'neg' as edge, 'C' from CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL
union all
select _id_ as id, end as ts, 'pos' as edge, 'C' from CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL
) where id between 0 and 10 order by ts 

"""


class Expr(object):
    def __init__(self, s):
        self.s = s

    def __str__(self, s):
        return str(self.s)


class ResultColumn(object):
    def __init__(self, expr=None, table_name=None, column_alias=None):
        self.expr = expr
        self.table_name = table_name
        self.column_alias = column_alias

    def __str__(self):
        if self.expr:
            s = str(self.expr)
            if self.column_alias:
                s += " AS"
                s += " " + str(self.column_alias)
            return s
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
        self.result_columns = list(result_columns)
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
