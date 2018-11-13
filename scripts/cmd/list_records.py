import click
import logging
from nvprof.db import Db
from nvprof.record import Runtime, ConcurrentKernel
from datetime import datetime

logger = logging.getLogger(__name__)


@click.command()
@click.argument('filename')
@click.option('--relative', is_flag=True)
@click.pass_context
def list_records(ctx, filename, relative):
    db = Db(filename)

    tables = [
        'CUPTI_ACTIVITY_KIND_RUNTIME',
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL',
    ]

    if relative:
        timestamp_offset, _ = db.get_extent()
    else:
        timestamp_offset = 0

    def norm(ts):
        return (ts - timestamp_offset) / 1e9

    for r in db.records(tables):
        if isinstance(r, Runtime):
            print("R {} {} {} {} {}".format(
                norm(r.start), norm(r.end), r.pid, r.tid, r.name()))
        elif isinstance(r, ConcurrentKernel):
            print("C {} {} {}".format(norm(r.start), norm(r.end), r.name))
