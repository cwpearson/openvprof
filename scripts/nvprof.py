""" Handle databases created by nvprof """

import sqlite3
import logging
from cupti.activity import Device

logger = logging.getLogger(__name__)


class Db(object):
    def __init__(self, filename=None, read_only=True):
        if read_only:
            # read-only
            uri_str = "file:"+filename+"?mode=ro"
            self.conn = sqlite3.connect(uri_str, uri=True)
        else:
            self.conn = sqlite3.connect(filename)
        self.version = self._get_version()
        if self.version != 11:
            logger.warn("Expecting version 11, Db may be unreliable")

    def get_cursor(self):
        return self.conn.cursor()

    def _get_version(self):
        return self.conn.execute("SELECT * from Version").fetchone()[0]

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
                    filter_str += " start >= {}".format(r[0])
                if r[0] and r[1]:
                    filter_str += " and "
                if r[1]:
                    filter_str += " end <= {}".format(r[1])
                filter_str += ")"
        return filter_str

    def get_strings(self):
        """ read StringTable from an nvprof db"""
        cursor = self.conn.cursor()
        id_to_string = {}
        string_to_id = {}
        for row in cursor.execute('SELECT * FROM StringTable'):
            id_, s = row

            id_to_string[id_] = s
            assert s not in string_to_id
            string_to_id[s] = id_
        return id_to_string, string_to_id

    def rows(self, table_name, columns=[]):
        if not columns:
            col_str = "*"
        else:
            col_str = ",".join(columns)
        return self.conn.execute("SELECT {} from {}".format(col_str, table_name))

    def multi_rows(self, table_names, start_ts=None, end_ts=None):
        return MultiTableRows(self, table_names, start_ts=start_ts, end_ts=end_ts)

    def execute(self, s):
        logger.debug("executing SQL: {}".format(s))
        return self.conn.execute(s)

    def num_rows(self, table_name, ranges=None):
        cmd = "SELECT Count(*) from {}".format(table_name)
        cmd += Db._range_filter_string(ranges)
        logger.debug("executing SQL: {}".format(cmd))
        return self.conn.execute(cmd).fetchone()[0]

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


loud = False


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
                sql_cmd += " start >= {}".format(start_ts)
            if start_ts and end_st:
                sql_cmd += " and"
            if end_ts:
                sql_cmd += " end <= {}".format(end_ts)
            sql_cmd += " ORDER BY start"
            logger.debug("executing {}".format(sql_cmd))
            cursor.execute(sql_cmd)
            logger.debug("done")
            self.cursors[table] = cursor
            self.next_rows[table] = cursor.fetchone()
        for table in self.next_rows:
            row = self.next_rows[table]
            if not row:
                continue
            if not self.current_ts:
                self.current_ts = row[0]
            self.current_ts = min(self.current_ts, row[0])

    def __iter__(self):
        return self

    def get_next_row(self, ts):
        """return table, row, start, and end that comes before or at ts"""
        next_table = None
        next_row = None

        to_remove = []
        for table in self.next_rows:
            if self.next_rows[table] is None:
                to_remove += [table]
        for table in to_remove:
            del(self.next_rows[table])

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

        # table, the actual row, start, and end
        if next_table:
            return next_table, next_row[2:], next_row[0], next_row[1]
        else:
            return None, None, None, None

    def __next__(self):
        # check all rows to see what the next time stamp is
        table, row, start, end = self.get_next_row(self.current_ts)
        if not table:
            raise StopIteration

        # print(table, row, ts, self.current_ts)
        assert start >= self.current_ts

        # get the next row from the table that has the next row
        self.next_rows[table] = self.cursors[table].fetchone()

        # update the current timestamp
        assert(start is not None)
        self.current_ts = start

        # return the table that produced the row, and the row
        return table, row, start, end
