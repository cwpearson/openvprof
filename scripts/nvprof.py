""" Handle databases created by nvprof """

import sqlite3
import logging

logger = logging.getLogger(__name__)


class Db(object):
    def __init__(self, filename=None):
        # read-only
        uri_str = "file:"+filename+"?mode=ro"
        self.conn = sqlite3.connect(uri_str, uri=True)

    def get_cursor(self):
        return self.conn.cursor()

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
        return self.cursor.execute("SELECT {} from {}".format(col_str, table_name))

    def multi_rows(self, table_names):
        return MultiTableRows(self, table_names)

    def execute(self, s):
        return self.cursor.execute(s)


loud = False


class MultiTableRows(object):
    def __init__(self, db, tables):
        self.cursors = {}
        self.next_rows = {}
        self.current_ts = 0
        for table in tables:
            cursor = db.get_cursor()
            sql_cmd = "SELECT start,end,* FROM {} ORDER BY start".format(table)
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
        return next_table, next_row[2:], next_row[0], next_row[1]

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
