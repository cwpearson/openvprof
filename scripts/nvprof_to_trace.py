#! env python3

import sqlite3
import sys
import json
import click
from math import log
import time

def table_size(cursor, table_name):
    cursor.execute('SELECT Count(*) FROM {}'.format(table_name))
    row = cursor.fetchone()
    return row[0]

def onelineplot( x, chars=u"▁▂▃▄▅▆▇█", sep=" " ):
    """ numbers -> v simple one-line plots like

f ▆ ▁ ▁ ▁ █ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁  osc 47  ▄ ▁ █ ▇ ▄ ▆ ▅ ▇ ▇ ▇ ▇ ▇ ▄ ▃ ▃ ▁ ▃ ▂  rosenbrock
f █ ▅ █ ▅ █ ▅ █ ▅ █ ▅ █ ▅ █ ▅ █ ▅ ▁ ▁ ▁ ▁  osc 58  ▂ ▁ ▃ ▂ ▄ ▃ ▅ ▄ ▆ ▅ ▇ ▆ █ ▇ ▇ ▃ ▃ ▇  rastrigin
f █ █ █ █ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁ ▁  osc 90  █ ▇ ▇ ▁ █ ▇ █ ▇ █ ▇ █ ▇ █ ▇ █ ▇ █ ▇  ackley

Usage:
    astring = onelineplot( numbers [optional chars= sep= ])
In:
    x: a list / tuple / numpy 1d array of numbers
    chars: plot characters, default the 8 Unicode bars above
    sep: "" or " " between plot chars

How it works:
    linscale x  ->  ints 0 1 2 3 ...  ->  chars ▁ ▂ ▃ ▄ ...

See also: https://github.com/RedKrieg/pysparklines
    """

    xlin = _linscale( x, to=[-.49, len(chars) - 1 + .49 ])
        # or quartiles 0 - 25 - 50 - 75 - 100
    xints = xlin.round().astype(int)
    assert xints.ndim == 1, xints.shape  # todo: 2d
    return sep.join([ chars[j] for j in xints ])

def histo(data, lower=None, upper=None):

    bins = {}

    if lower:
        lower_bound = int(math.log(lower))
    if upper:
        upper_bound = int(math.log(upper))

    bins = []
    for e in data:
        l = int(math.log(e, 2))
        if lower:
            if l < lower_bound:
                l = lower_bound
        if upper:
            if l > upper_bound:
                l = upper_bound
        if l not in bins:
            bins[l] = 0
        bins[l] += 1

    return []

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
    chars=u"▁▂▃▄▅▆▇█"
    if log:
        ids = lognorm(x, len(chars))
    else:
        ids = linnorm(x, len(chars))
    return "".join([chars[i] for i in ids])

@click.group()
def cli():
    pass

@click.command()
@click.argument('filename')
def driver_time(filename):
    conn = sqlite3.connect(filename)
    c = conn.cursor()
    print("CUPTI_ACTIVITY_KIND_DRIVER has {} entries".format(table_size(c, 'CUPTI_ACTIVITY_KIND_DRIVER')), file=sys.stderr)

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
    print("Elapsed: {}s".format( (last-first)/1e9 )) # time between first and last event
    histo, lower, upper = histo.get()
    print("Durations: 2^{} {} 2^{}".format(lower, spark(histo), upper))
    

@click.command()
@click.argument('filename')
@click.option('--scale', type=click.Choice(['lin', 'log']), default='lin', show_default=True)
def kernel_time(filename, scale):
    conn = sqlite3.connect(filename)
    c = conn.cursor()
    print("CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL has {} entries".format(table_size(c, 'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL')), file=sys.stderr)

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
    # print("First event start: {}".format(  time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(first//1e9))  ))
    # print("Last event end: {}".format(  time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last//1e9))  ))
    print("Elapsed: {}s".format( (last-first)/1e9 )) # time between first and last event
    histo, lower, upper = histo.get()
    if scale == "lin":
        sparkstring = spark(histo, log=False)
    else:
        sparkstring = spark(histo, log=True)
    print("Durations: 2^{} {} 2^{}".format(lower, sparkstring, upper))


cli.add_command(driver_time)
cli.add_command(kernel_time)

if __name__ == '__main__':
    cli()

"""



for row in c.execute('PRAGMA table_info(CUPTI_ACTIVITY_KIND_DRIVER)'):
    print(row, file=sys.stderr)

print("CUPTI_ACTIVITY_KIND_DRIVER has {} entries".format(table_size(c, 'CUPTI_ACTIVITY_KIND_DRIVER')), file=sys.stderr)
print("CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL has {} entries".format(table_size(c, 'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL')), file=sys.stderr)

sys.exit()

cupti_activity_driver_start = None

for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_DRIVER"):
    start_ns = row[3]
    if not cupti_activity_driver_start:
        cupti_activity_driver_start = start_ns
    cupti_activity_driver_start = min(cupti_activity_driver_start, start_ns)


trace = {
    "traceEvents": [],
    "displayTimeUnit": "ns",
}

# add driver events

for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_DRIVER"):
    start_ns = row[3]
    dur_ns = row[4] - row[3]

    j = {
        "name": "name",
        "cat": "cat",
        "ph": "X",
        "pid": "pid",
        "tid": "tid",
        "ts": start_ns // 1000,
        "dur": dur_ns // 1000,        "args": {},
        # "tdur": dur,
    }
    trace["traceEvents"] += [j]

# add concurrent kernels to timeline
for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL"):
    start_ns = row[3]
    dur_ns = row[4] - row[3]

    j = {
        "name": "name",
        "cat": "cat",
        "ph": "X",
        "pid": "pid",
        "tid": "tid",
        "ts": start_ns // 1000,
        "dur": dur_ns // 1000,
        "args": {},
        # "tdur": dur,
    }
    trace["traceEvents"] += [j]

s = json.dumps(trace, indent=4)
print(s)
"""