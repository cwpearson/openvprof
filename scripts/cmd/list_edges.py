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
def list_edges(ctx, filename, relative):
    db = Db(filename)

    tables = [
        'CUPTI_ACTIVITY_KIND_RUNTIME',
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL',
        'CUPTI_ACTIVITY_KIND_MEMCPY',
        'CUPTI_ACTIVITY_KIND_MEMCPY2',
        'CUPTI_ACTIVITY_KIND_MARKER',
    ]

    if relative:
        timestamp_offset, _ = db.get_extent()
    else:
        timestamp_offset = 0

    def norm(ts):
        return (ts - timestamp_offset) / 1e9

    for e in db.multi_edges_records(tables):
        print(e)
