import click
import sqlite3
import logging
import sys
import os

from nvprof.db import Db

logger = logging.getLogger(__name__)


@click.command()
@click.argument('filename', type=click.Path(exists=True))
@click.pass_context
def stats(ctx, filename):

    print("file {}".format(filename))
    sz = os.path.getsize(filename)
    print('size {}MB'.format(sz/1024/1024))

    db = Db(filename)

    first_timestamp, last_timestamp = db.get_extent()

    print("first timestamp: {}".format(first_timestamp))
    print("last timestamp: {}".format(last_timestamp))
    elapsed = (last_timestamp - first_timestamp) / 1e9
    print("nvprof time: {}s".format(elapsed))

    tables = {
        'CUPTI_ACTIVITY_KIND_RUNTIME': "runtime",
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL': "concurrent_kernel",
        'CUPTI_ACTIVITY_KIND_KERNEL': "kernel",
        'CUPTI_ACTIVITY_KIND_MARKER': "marker",
        'CUPTI_ACTIVITY_KIND_DRIVER': "driver",
        'CUPTI_ACTIVITY_KIND_MEMCPY': "memcpy",
        'CUPTI_ACTIVITY_KIND_MEMCPY2': "memcpy2",
    }

    for table, name in tables.items():
        num_rows = db.num_rows(table)
        print("stats\t{}\t{}".format(name, num_rows))
