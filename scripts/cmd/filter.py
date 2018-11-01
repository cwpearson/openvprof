from shutil import copyfile
import logging
import click
from nvprof import Db
import os

logger = logging.getLogger(__name__)


@click.command()
@click.argument('input')
@click.argument('output')
@click.argument('start')
@click.argument('end')
@click.pass_context
def filter(ctx, input, output, start, end):
    """filter file INPUT to contain only records between START and END"""

    copyfile(input, output)

    input_size = os.path.getsize(input)
    logger.debug(
        "copied {}MB {} -> {}".format(int(input_size/1e6), input, output))

    db = Db(output, read_only=False)

    tables = [
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL',
        'CUPTI_ACTIVITY_KIND_MEMCPY',
        'CUPTI_ACTIVITY_KIND_KERNEL',
        'CUPTI_ACTIVITY_KIND_RUNTIME',
    ]

    for table in tables:
        sql_cmd = "DELETE FROM {} WHERE (end <= {}) or (start >= {})".format(
            table, start, end)
        logger.debug(sql_cmd)
        db.execute(sql_cmd)

    db.commit()
    logger.debug("vacuuming...")
    db.vacuum()

    output_size = os.path.getsize(output)
    logger.debug("reduced output size to {}MB".format(
        int(output_size/1e6)))
