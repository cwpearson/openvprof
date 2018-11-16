import click
import sqlite3
import json
import logging
import gzip
import sys
import time

logger = logging.getLogger(__name__)


@click.command()
@click.argument('filename')
@click.option('--gzip/--no-gzip', 'gz_', default=True, help='use gzip compression')
@click.option('--runtime/--no-runtime', default=True)
@click.option('--kernel/--no-kernel', default=True)
@click.argument('out', type=click.File('wb'), default="-")
def timeline(filename, gz_, runtime, kernel, out):
    """Generate a chrome:://tracing-compatible file from a nvprof trace.

    \b
    FILENAME: an nvprof trace file
    OUT: an output file (default = stdout)
    """

    conn = sqlite3.connect(filename)
    c = conn.cursor()

    if gz_:
        logger.info("Using gzip compression")
        f = gzip.GzipFile(mode='wb', fileobj=out)
    else:
        f = out

    def _write(s):
        f.write(s.encode('utf-8'))

    _write('{\n"displayTimeUnit": "ns",\n"traceEvents": [\n')

    comma_first = False
    # add CONCURRENT_KERNELS to timeline
    if kernel:
        num_rows = 0
        wall_start = time.time()
        logger.info("CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL...")
        for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL"):
            start_ns, end_ns, name = *row[6:8], row[24]
            j = {
                "name": str(name),
                "cat": "cat",
                "ph": "X",
                "pid": "CONCURRENT_KERNEL",
                "tid": "tid",
                "ts": start_ns // 1000,
                "dur": (end_ns - start_ns) // 1000,
                "args": {},
                # "tdur": dur,
            }

            if comma_first:
                s = ",\n"
            else:
                s = ""
            s += json.dumps(j)
            _write(s)
            comma_first = True
            num_rows += 1
        logger.info("{} rows at {} rows/sec".format(num_rows, num_rows /
                                                    (time.time() - wall_start)))

    if runtime:
        num_rows = 0
        wall_start = time.time()
        logger.info("CUPTI_ACTIVITY_KIND_RUNTIME...")
        for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_RUNTIME"):
            cbid, start_ns, end_ns, pid, tid = row[1:6]
            if tid < 0:
                tid += 2**32
            # logger.debug("{} {} {} {} {}".format(
            #     cbid, start_ns, end_ns, pid, tid))

            j = {
                "name": str(cbid),
                "cat": "cat",
                "ph": "X",
                "pid": "RUNTIME " + str(pid),
                "tid": tid,
                "ts": start_ns // 1000,
                "dur": (end_ns - start_ns) // 1000,
                "args": {},
            }

            if comma_first:
                s = ",\n"
            s += json.dumps(j)
            _write(s)
            comma_first = True
            num_rows += 1
        logger.info("{} rows at {} rows/sec".format(num_rows, num_rows /
                                                    (time.time() - wall_start)))

    _write("\n]\n")
    _write("}\n")

    f.close()
