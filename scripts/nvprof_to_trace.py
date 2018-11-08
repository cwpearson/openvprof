#! env python3

import sqlite3
import sys
import json
import click
from math import log
import logging
import time

import cmd.summary
import cmd.list_ranges
import cmd.summary_new
import cmd.filter
import cmd.list_records

logger = logging.getLogger(__name__)


def table_size(cursor, table_name):
    cursor.execute('SELECT Count(*) FROM {}'.format(table_name))
    row = cursor.fetchone()
    return row[0]


class Histogram(object):
    def __init__(self, lower=None, upper=None):
        if lower:
            self.lower_bound = int(math.log(lower))
        else:
            self.lower_bound = None
        if upper:
            self.upper_bound = int(math.log(upper))
        else:
            self.upper_bound = None
        self.bins = {}

    def insert(self, e):
        l = int(log(e, 2))
        if self.lower_bound:
            if l < lower_bound:
                l = lower_bound
        if self.upper_bound:
            if l > upper_bound:
                l = upper_bound
        if l not in self.bins:
            self.bins[l] = 0
        self.bins[l] += 1

    def get(self):
        max_key = max(self.bins.keys())
        min_key = min(self.bins.keys())
        return [self.bins[i] if i in self.bins else 0 for i in range(min_key, max_key+1)], min_key, max_key


def linnorm(x, to):
    """x, linearly scaled f-> [0,to]"""
    lower = min(x)
    upper = max(x)
    raw = [((e - lower) * to) // (upper - lower) for e in x]
    raw = [e if e != to else e-1 for e in raw]
    return raw


def lognorm(x, to):
    """log of x, linearly scaled -> [0,to]"""
    x = [0 if e == 0 else log(e) for e in x]
    lower = min(x)
    upper = max(x)
    raw = [((e - lower) * to) / (upper - lower) for e in x]
    raw = [int(e) for e in raw]
    raw = [e if e != to else e-1 for e in raw]
    return raw


def spark(x, log=False):
    chars = u"▁▂▃▄▅▆▇█"
    if log:
        ids = lognorm(x, len(chars))
    else:
        ids = linnorm(x, len(chars))
    return "".join([chars[i] for i in ids])


@click.group()
@click.option('--debug', is_flag=True, help="print debugging messages")
@click.pass_context
def cli(ctx, debug):
    logging.basicConfig()
    ctx.ensure_object(dict)
    ctx.obj["DEBUG"] = debug
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


@click.command()
@click.argument('filename')
@click.pass_context
def driver_time(ctx, filename):
    """Show a histogram of driver API times"""
    logging.debug("Opening {}".format(filename))
    conn = sqlite3.connect(filename)
    c = conn.cursor()
    if ctx.obj["DEBUG"]:
        logging.debug("table CUPTI_ACTIVITY_KIND_DRIVER has {} entries".format(
            table_size(c, 'CUPTI_ACTIVITY_KIND_DRIVER')))

    first = None
    last = None
    histo = Histogram()
    for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_DRIVER"):
        start_ns = row[2]
        end_ns = row[3]
        if not first:
            first = start_ns
        if not last:
            last = start_ns
        first = min(first, start_ns)
        last = max(last, start_ns)
        histo.insert(end_ns - start_ns)
    # print("First event start: {}".format(  time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(first//1e9))  ))
    # print("Last event end: {}".format(  time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last//1e9))  ))
    logging.debug("first event timestamp {}ns".format(first))
    logging.debug("last event timestamp {}ns".format(last))
    histo, lower, upper = histo.get()
    print("Durations: 2^{} {} 2^{}".format(lower, spark(histo), upper))


@click.command()
@click.argument('filename')
@click.option('--scale', type=click.Choice(['lin', 'log']), default='lin', show_default=True)
@click.pass_context
def kernel_time(ctx, filename, scale):
    """Show a histogram of kernel times (ns)"""
    logging.debug("Opening {}".format(filename))
    conn = sqlite3.connect(filename)
    c = conn.cursor()
    if ctx.obj["DEBUG"]:
        logging.debug("table CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL has {} entries".format(
            table_size(c, 'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL')))

    first = None
    last = None
    histo = Histogram()
    for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL"):
        start_ns = row[6]
        end_ns = row[7]
        if not first:
            first = start_ns
        if not last:
            last = start_ns
        first = min(first, start_ns)
        last = max(last, start_ns)
        histo.insert(end_ns - start_ns)
    histo, lower, upper = histo.get()
    logging.debug("lower bound is {}".format(lower))
    logging.debug("upper bound is {}".format(upper))
    logging.debug("histogram data: {}".format(histo))
    if scale == "lin":
        logging.debug("Using linear y-axis scale")
        sparkstring = spark(histo, log=False)
    else:
        logging.debug("Using logarithmic y-axis scale")
        sparkstring = spark(histo, log=True)
    print("Durations: 2^{} {} 2^{}".format(lower, sparkstring, upper))


@click.command()
@click.argument('filename')
@click.option('--to')
@click.option('--from', '_from')
def timeline(filename, _from, to):
    """Generate a chrome:://tracing timeline"""

    conn = sqlite3.connect(filename)
    c = conn.cursor()

    if to:
        try:
            to = float(to)
        except ValueError:
            print("to should be a float", file=sys.stderr)
            sys.exit(-1)

    if _from:
        try:
            _from = float(_from)
        except ValueError:
            print("from should be a float", file=sys.stderr)
            sys.exit(-1)

    trace = {
        "traceEvents": [],
        "displayTimeUnit": "ns",
    }

    # add KERNELS to timeline
    for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL"):
        start_ns = row[6]
        end_ns = row[7]
        if _from and start_ns < _from:
            continue
        if to and end_ns > to:
            continue
        j = {
            "name": "name",
            "cat": "cat",
            "ph": "X",
            "pid": "CONCURRENT_KERNEL",
            "tid": "tid",
            "ts": start_ns // 1000,
            "dur": (end_ns - start_ns) // 1000,
            "args": {},
            # "tdur": dur,
        }
        trace["traceEvents"] += [j]

    s = json.dumps(trace, indent=4)
    print(s)


cli.add_command(timeline)
cli.add_command(driver_time)
cli.add_command(kernel_time)
cli.add_command(cmd.summary.summary)
cli.add_command(cmd.summary_new.summary_new)
cli.add_command(cmd.list_ranges.list_ranges)
cli.add_command(cmd.list_records.list_records)
cli.add_command(cmd.filter.filter)

if __name__ == '__main__':
    cli()
