""" Handle databases created by nvprof """

import sqlite3
import logging
from nvprof.record import Device, Runtime, ConcurrentKernel, Memcpy, Range
from nvprof.sql import Select
import copy
import sys

logger = logging.getLogger(__name__)

"""
select Min(start) from
(
select Min(start) as start from CUPTI_ACTIVITY_KIND_DRIVER
union
select Min(start) as start from CUPTI_ACTIVITY_KIND_RUNTIME
) as start
"""


class Db(object):
    def __init__(self, filename=None, read_only=True):
        self.next_view_id = -1
        if read_only:
            # read-only
            uri_str = "file:"+filename+"?mode=ro"
            self.conn = sqlite3.connect(uri_str, uri=True)
        else:
            self.conn = sqlite3.connect(filename)
        self.version = self._get_version()
        if self.version != 11:
            logger.warn("Expecting version 11, Db may be unreliable")

        # create an abstraction over CUPTI markers that describe a time range that mirrors other CUPTI types
        self._create_range_table()

    def __del__(self):
        self._release_range_table()

    def get_unique_name(self):
        self.next_view_id += 1
        return "view" + str(self.next_view_id)

    def _create_range_table(self):
        sql = """
CREATE TEMPORARY TABLE CUPTI_ACTIVITY_KIND_RANGE AS
WITH rows AS (
    SELECT start, end, name, domain from (
    SELECT
    count(*) as num_markers,
    Min(timestamp) as start,
    Max(timestamp) as end,
    Max(name) as name,
    domain
    FROM CUPTI_ACTIVITY_KIND_MARKER group by id
    ) where num_markers == 2
) SELECT * FROM rows"""
        self.execute(sql)

    def _release_range_table(self):
        sql = "DROP TABLE CUPTI_ACTIVITY_KIND_RANGE"
        self.execute(sql)

    def get_cursor(self):
        return self.conn.cursor()

    def _get_version(self):
        return self.conn.execute(str(Select("Version"))).fetchone()[0]

    def get_first_start(self):
        """return the first timestamp found in a variety of tables"""
        first = float('Inf')

        start_end_tables = [
            "CUPTI_ACTIVITY_KIND_RUNTIME",
            "CUPTI_ACTIVITY_KIND_DRIVER",
            "CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL",
            "CUPTI_ACTIVITY_KIND_MEMCPY",
            "CUPTI_ACTIVITY_KIND_MEMCPY2",
            "CUPTI_ACTIVITY_KIND_KERNEL",
            'CUPTI_ACTIVITY_KIND_RANGE',
        ]

        for t in start_end_tables:
            sql = Select(t)
            sql.ResultColumn(expr="Min(start)")
            result = self.execute(sql).fetchone()[0]
            if result:
                first = min(first, result)
        return first

    def _range_filter_string(ranges):
        if not ranges:
            return ""
        filter_str = ""
        for r in ranges:
            if r[0] or r[1]:
                filter_str = " WHERE"
                break
        for r in ranges:
            if r[0] or r[1]:
                filter_str += " ("
                assert len(r) == 2
                if r[0]:
                    filter_str += " end >= {}".format(r[0])
                if r[0] and r[1]:
                    filter_str += " and "
                if r[1]:
                    filter_str += " start <= {}".format(r[1])
                filter_str += ")"
        return filter_str

    def get_strings(self):
        return self.read_strings()

    def read_strings(self):
        """ read StringTable from an nvprof db"""
        cursor = self.conn.cursor()
        id_to_string = {}
        string_to_id = {}
        cmd = Select("StringTable")
        for row in cursor.execute(str(cmd)):
            id_, s = row
            id_to_string[id_] = s
            assert s not in string_to_id
            string_to_id[s] = id_
        return id_to_string, string_to_id

    def rows(self, table_name, columns=['*']):
        col_str = ",".join(columns)
        return self.conn.execute("SELECT {} from {}".format(col_str, table_name))

    def multi_rows(self, table_names, start_ts=None, end_ts=None):
        return MultiTableRows(self, table_names, start_ts=start_ts, end_ts=end_ts)

    def execute(self, s):
        s = str(s)
        logger.debug("executing SQL: {}".format(s))
        cursor = self.conn.cursor()
        return cursor.execute(s)

    def num_rows(self, table_name, ranges=None):
        cmd = "SELECT Count(*) from {}".format(table_name)
        cmd += Db._range_filter_string(ranges)
        logger.debug("executing SQL: {}".format(cmd))
        return self.conn.execute(cmd).fetchone()[0]

    def num_edges(self, table_name, ranges=None):
        """return the number of edges contained within [r] for r in ranges"""

    def get_devices(self):
        # look for unique devices in CUPTI_ACTIVITY_KIND_DEVICE
        devices = []
        for row in self.conn.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_DEVICE"):
            devices += [Device(id_=row[26])]
        return devices

    def commit(self):
        self.conn.commit()

    def vacuum(self):
        self.execute("vacuum")

    def add_range(self, name, domain, start, stop):
        self.add_marker(name, domain, start)
        self.add_marker(name, domain, stop)

    def add_marker(name, domain, ts):
        raise NotImplementedError
        # make sure name is in strings table
        # make sure domain is in strings table
        # add marker

    def records(self, table_names, start_ts=None, end_ts=None):

        strings, _ = self.get_strings()

        for table, row, _, _ in MultiTableRows(self, table_names, start_ts, end_ts):
            if table in table_names:
                if table == "CUPTI_ACTIVITY_KIND_RUNTIME":
                    yield Runtime.from_nvprof_row(row)
                elif table == "CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL":
                    yield ConcurrentKernel.from_nvprof_row(row, strings)
                elif table == "CUPTI_ACTIVITY_KIND_RANGE":
                    yield Range.from_nvprof_row(row, strings)
                else:
                    logger.error("unhandled table {}".format(table))
                    raise SystemExit(-1)

    def table_exists(self, table):
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';".format(
            table=table)
        row = self.execute(sql).fetchone()[0]
        if row:
            return True
        return False

    def ranges_with_name(self, range_names):
        assert len(range_names) > 0
        view_name = self.get_unique_name()
        sql = """CREATE TEMP TABLE {} as
select
  CUPTI_ACTIVITY_KIND_RANGE.*
from
  CUPTI_ACTIVITY_KIND_RANGE
  INNER JOIN StringTable on CUPTI_ACTIVITY_KIND_RANGE.name = StringTable._id_
  where StringTable.value like '%{}%'""".format(view_name, range_names[0])
        for name in range_names[1:]:
            sql += "\n  or StringTable.value like '%{}%'".format(name)
        self.execute(sql)
        return view_name

    def rows_in_ranges(self, table, ranges_view):
        """ create a view that has rows from table that are in RANGES_VIEW"""
        new_view = self.get_unique_name()
        sql = """CREATE TEMP VIEW {2} AS
SELECT DISTINCT
  {0}.*
FROM
  {0}
JOIN
  {1}
where
  {0}.start BETWEEN {1}.start and {1}.end
  and {0}.end BETWEEN {1}.start and {1}.end""".format(table, ranges_view, new_view)

        self.execute(sql)
        return new_view

    def rows_overlap_ranges(self, table, ranges_view):
        """ create a view that has rows from table that overlap ranges in RANGES_VIEW"""
        new_view = self.get_unique_name()
        sql = """CREATE TEMP VIEW {2} AS
SELECT DISTINCT
  {0}.*
FROM
  {0}
JOIN
  {1}
where
  {0}.start BETWEEN {1}.start and {1}.end
  or {0}.end BETWEEN {1}.start and {1}.end
  or {1}.end BETWEEN {0}.start and {0}.end""".format(table, ranges_view, new_view)

        self.execute(sql)
        return new_view

    def edges_from_rows(self, rows_view):
        new_view = self.get_unique_name()
        sql = """CREATE TEMP VIEW {0} AS
SELECT
  {1}.start as ts,
  1 as edge,
  * 
FROM {1}
UNION ALL
SELECT
  {1}.end as ts,
  0 as edge,
  *
FROM {1}
order by ts""".format(new_view, rows_view)

        self.execute(sql)
        return new_view

    def create_filtered_table(self, table, range_names=None):
        if range_names:
            # create a view which has ranges with a name like range_names
            ranges_view = self.ranges_with_name(range_names)

            # create a view that has rows that fall in ranges in a view
            rows_view = self.rows_overlap_ranges(table, ranges_view)
            return rows_view
        else:
            return table

    def create_edges_view(self, view):
        out_view = self.get_unique_name()
        sql = """CREATE TEMP VIEW {0} AS
SELECT {1}.start as ts, 1 as edge, * from {1}
UNION ALL
select {1}.end as ts, 0 as edge, * from {1}""".format(out_view, view)
        self.execute(sql)
        return out_view

#     def _rows_in_range_name(self, table, range_names):
#         """sql to select all columns from 'table' where 'table'.start and table.'end' fall
#         within a range that has a name like range_names.
#         If a row is in multiple ranges, only one is returned
#         """

#         matching_ranges_query = self._ranges_by_name_query(range_names)

#         # DISTINCT because if a row is in multiple ranges we only want to see it once
#         sql = """SELECT DISTINCT
#   {0}.*
# from
#   {0}
# JOIN
# (
# {1}
# ) as CUPTI_ACTIVITY_KIND_RANGE
# where
#   {0}.start BETWEEN CUPTI_ACTIVITY_KIND_RANGE.start and CUPTI_ACTIVITY_KIND_RANGE.end
#   and {0}.end BETWEEN CUPTI_ACTIVITY_KIND_RANGE.start and CUPTI_ACTIVITY_KIND_RANGE.end""".format(table, matching_ranges_query)
#         return sql

#     def _rows_to_edges(self, table, range_names=None):

#         if range_names:
#             row_sql = self._rows_in_range_name(table, range_names)
#         else:
#             row_sql = "SELECT * in {0}".format(table)

#         convert_to_edges_sql = """select {0}.start as ts, 1 as edge, * from ({1}) as {0}
# UNION ALL
# select {0}.end as ts, 0 as edge, * from ({1}) as {0}
# order by ts""".format(table, row_sql)

#         return convert_to_edges_sql

    # def _edges_sql(self, table, start_ts=None, end_ts=None):
    #     sql_start_end_where = ""
    #     if start_ts:
    #         sql_start_end_where += " where end >= {}".format(start_ts)
    #     if start_ts and end_ts:
    #         sql_start_end_where += " and"
    #     if end_ts:
    #         sql_start_end_where += " where start <= {}", format(end_ts)

    #     def _start_end_posedge(table):
    #         return "select start as ts, 1 as edge, * from {}{}".format(table, sql_start_end_where)

    #     def _start_end_negedge(table):
    #         return "select end as ts, 0 as edge, * from {}{}".format(table, sql_start_end_where)

    #     posedge_func = _start_end_posedge
    #     negedge_func = _start_end_negedge
    #     subquery = "("
    #     subquery += "\n" + posedge_func(table)
    #     subquery += "\n" + "UNION ALL"
    #     subquery += "\n" + negedge_func(table)
    #     subquery += "\n)"
    #     sql = Select(table_or_subquery=subquery, ordering_terms=["ts"])
    #     return sql

    def edges(self, table, start_ts=None, end_ts=None):
        sql = self._edges_sql(table, start_ts, end_ts)
        return self.execute(sql)

    def num_edges(self, table, start_ts=None, end_ts=None):
        sql = self._edges_sql(table, start_ts, end_ts)
        sql.result_columns = ["Count(*)"]
        return self.execute(sql).fetchone()[0]

#     def _ranges_by_name_query(self, range_names):
#         """return sql select statement that produces results with (name, start, end) for any range with range_names in the name"""
#         assert len(range_names) > 0
#         sql = """select
#   CUPTI_ACTIVITY_KIND_RANGE.*
# from
#   CUPTI_ACTIVITY_KIND_RANGE
#   INNER JOIN StringTable on CUPTI_ACTIVITY_KIND_RANGE.name = StringTable._id_
#   where StringTable.value like '%{}%'""".format(range_names[0])
#         for name in range_names[1:]:
#             sql += "\n  or StringTable.value like '%{}%'".format(name)
#         return sql

    def multi_edges(self, table_names, start_ts=None, end_ts=None):
        edges = {}
        next_edges = {}
        for table in table_names:
            edges[table] = self.edges(table, start_ts=start_ts, end_ts=end_ts)
            next_edges[table] = edges[table].fetchone()

        while True:
            # clean up any tables that have no more rows
            to_remove = []
            for table, edge in next_edges.items():
                if edge is None:
                    to_remove += [table]
            for table in to_remove:
                logger.debug("no more rows in {}".format(table))
                del(edges[table])
                del(next_edges[table])

            yield_edge = None
            yield_table = None
            for table, edge in next_edges.items():
                if not yield_table:
                    yield_edge = edge
                    yield_table = table
                else:
                    if edge[0] < yield_edge[0]:
                        yield_edge = edge
                        yield_table = table
            if not yield_table:
                break

            next_edges[yield_table] = edges[yield_table].fetchone()
            yield yield_table, yield_edge

    def multi_ordered_edges_records(self, edge_tables, row_factories={}):
        for table, edge in self.multi_ordered_edges(edge_tables):
            yield edge[0], edge[1], row_factories[table](edge[2:])

    def multi_ordered_edges(self, edge_tables):

        edges = {}
        next_edges = {}
        for table in edge_tables:
            edges[table] = self.ordered_edges(table)
            next_edges[table] = edges[table].fetchone()

        while True:
            # clean up any tables that have no more rows
            to_remove = []
            for table, edge in next_edges.items():
                if edge is None:
                    to_remove += [table]
            for table in to_remove:
                logger.debug("no more rows in {}".format(table))
                del(edges[table])
                del(next_edges[table])

            yield_edge = None
            yield_table = None
            for table, edge in next_edges.items():
                if not yield_table:
                    yield_edge = edge
                    yield_table = table
                else:
                    if edge[0] < yield_edge[0]:
                        yield_edge = edge
                        yield_table = table
            if not yield_table:
                break

            next_edges[yield_table] = edges[yield_table].fetchone()
            yield yield_table, yield_edge

    def ordered_edges(self, edge_table):
        return self.execute('SELECT * FROM {} ORDER BY ts'.format(edge_table))


class MultiTableRows(object):
    def __init__(self, db, tables, start_ts=None, end_ts=None):
        self.cursors = {}
        self.next_rows = {}
        self.current_ts = 0
        for table in tables:
            cursor = db.get_cursor()
            sql_cmd = "SELECT start,end,* FROM {}".format(table)
            if start_ts or end_ts:
                sql_cmd += " where"
            if start_ts:
                sql_cmd += " end >= {}".format(start_ts)
            if start_ts and end_ts:
                sql_cmd += " and"
            if end_ts:
                sql_cmd += " start <= {}".format(end_ts)
            sql_cmd += " ORDER BY start"
            logger.debug("executing {}".format(sql_cmd))
            # read the first row
            cursor.execute(sql_cmd)
            next_row = cursor.fetchone()
            # if there is a row, keep this cursor
            if next_row is not None:
                self.cursors[table] = cursor
                self.next_rows[table] = next_row
        for table in self.next_rows:
            row = self.next_rows[table]
            if not self.current_ts:
                self.current_ts = row[0]
            self.current_ts = min(self.current_ts, row[0])

    def __iter__(self):
        return self

    def get_next_row(self, ts):
        """return table, row, start, and end that comes before or at ts"""
        next_table = None
        next_row = None

        # to_remove = []
        # for table in self.next_rows:
        #     if self.next_rows[table] is None:
        #         to_remove += [table]
        # for table in to_remove:
        #     del(self.next_rows[table])

        # search all tables for the soonest timestamp
        for table in self.next_rows:
            row = self.next_rows[table]

            if not next_table:
                next_table = table
                next_row = row

            # expect to get rows in ascending order of start time
            assert row[0] >= self.current_ts

            if row[0] < next_row[0]:
                # print(table, "is later at", end)
                next_table = table
                next_row = row

        # if we found a next row, read the future next_row from the db
        # if there is no future next row, discard the table
        if next_table is not None:
            future_row = self.cursors[next_table].fetchone()
            if future_row is not None:
                self.next_rows[next_table] = future_row
            else:
                del(self.next_rows[next_table])
                del(self.cursors[next_table])

        # table, the actual row, start, and end
        if next_table:
            return next_table, next_row[2:], next_row[0], next_row[1]
        else:
            return None, None, None, None

    def __next__(self):
        # get the table and row for the next time stamp
        table, row, start, end = self.get_next_row(self.current_ts)
        if not table:
            raise StopIteration

        # print(table, row, ts, self.current_ts)
        assert start >= self.current_ts

        # update the current timestamp
        assert start is not None
        self.current_ts = start

        # return the table that produced the row, and the row
        return table, row, start, end
