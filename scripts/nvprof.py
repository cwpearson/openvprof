""" Handle databases created by nvprof """

import sqlite3


class Db(object):
    def __init__(self, filename=None):
        # read-only
        uri_str = "file:"+filename+"?mode=ro"
        self.conn = sqlite3.connect(uri_str, uri=True)
        self.cursor = self.conn.cursor()

    def get_strings(self):
        """ read StringTable from an nvprof db"""
        id_to_string = {}
        string_to_id = {}
        for row in self.cursor.execute('SELECT * FROM StringTable'):
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

    def execute(self, s):
        return self.cursor.execute(s)
