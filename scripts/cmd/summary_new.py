import click
import copy
import sqlite3
import logging
import sys
import time
from math import ceil
from collections import defaultdict
from enum import Enum
import heapq

import cupti.activity_memory_kind
from nvprof import Db

logger = logging.getLogger(__name__)


class Heap(object):
    def __init__(self):
        self.items = []

    def push(self, element, priority):
        entry = (priority, element)
        heapq.heappush(self.items, entry)

    def pop(self):
        return heapq.heappop(self.items)

    def peek(self):
        priority, element = self.items[0]
        return priority, element

    def __len__(self):
        return len(self.items)


class Timeline(object):

    def __init__(self, multi_active=True):
        self.num_active = 0
        self.time = 0.0
        self.active_start = None
        self.multi_active = multi_active

    def idle(self, ts):
        if not self.multi_active:
            assert self.num_active == 1
        self.num_active -= 1
        if self.num_active == 0:
            self.time += (ts - self.active_start)

    def active(self, ts):
        if not self.multi_active:
            if self.num_active != 0:
                logger.error(
                    "state was not idle when set active at {}".format(ts))
            assert False
        if self.num_active == 0:
            self.active_start = ts
        self.num_active += 1

    def is_active(self):
        return self.num_active > 0


class NestedTimeline(object):
    def __init__(self):
        self.timelines = defaultdict(lambda: Timeline())
        self.time = 0.0

    def _any_active(self):
        return any(self.timelines[key].is_active() for key in self.timelines)

    def _all_idle(self):
        return all(not self.timelines[key].is_active() for key in self.timelines)

    def set_active(self, key, ts):
        if not self._any_active():
            self.active_start = ts
        self.timelines[key].active(ts)

    def set_idle(self, key, ts):
        self.timelines[key].idle(ts)
        if self._all_idle():
            self.time += (ts - self.active_start)

    def is_active(self):
        return self._any_active()


@click.command()
@click.argument('filename')
@click.option('-b', '--begin', help='Only consider events that begin after this time')
@click.option('-e', '--end', help='Only consider records that end before this time')
@click.pass_context
def summary_new(ctx, filename, begin, end):

    db = Db(filename)

    logger.debug("Loading strings")
    nvprof_id_to_string, nvprof_string_to_id = db.get_strings()

    if end:
        logger.debug("using end = {}".format(end))
    if begin:
        logger.debug("using begin = {}".format(begin))

    tables = [
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL',
        # 'CUPTI_ACTIVITY_KIND_MEMCPY',
        # 'CUPTI_ACTIVITY_KIND_MEMCPY2',
        'CUPTI_ACTIVITY_KIND_KERNEL',
        # 'CUPTI_ACTIVITY_KIND_DRIVER',
        'CUPTI_ACTIVITY_KIND_RUNTIME',
    ]

    total_rows = 0
    for table in tables:
        total_rows += db.num_rows(table)
    logger.debug("{} rows".format(total_rows))

    iter_column = 'start'

    total_runtime = 0
    total_driver = 0
    total_kernel = 0
    total_memcpy = 0

    IDLE = 0
    BUSY = 1
    START = 'op_start'
    STOP = 'op_stop'

    gpu_kernels = NestedTimeline()  # indexed by GPU
    comm_states = NestedTimeline()  # indexed by GPU
    driver_state = NestedTimeline()  # indexed by tid
    runtime_states = NestedTimeline()  # indexed by tid

    queue = []

    def consume(table, row, op):
        nonlocal total_runtime
        nonlocal total_driver
        nonlocal gpu_kernels
        nonlocal total_memcpy
        nonlocal runtime_states

        if table == "CUPTI_ACTIVITY_KIND_RUNTIME":
            start = row[2]
            end = row[3]
            tid = row[5]
            if op == START:
                runtime_states.set_active(tid, start)
            else:
                runtime_states.set_idle(tid, end)
        # elif table == "CUPTI_ACTIVITY_KIND_DRIVER":
            #cbid = row[1]
            #start = row[2]
            #end = row[3]
            #process_id = row[4]
            #thread_id = row[5]
            #correlation_id = row[6]
        elif table == "CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL" or table == "CUPTI_ACTIVITY_KIND_KERNEL":
            start = row[6]
            end = row[7]
            device_id = row[9]
            if op == START:
                gpu_kernels.set_active(device_id, start)
            else:
                gpu_kernels.set_idle(device_id, end)
        # elif table == "CUPTI_ACTIVITY_KIND_MEMCPY":
        #     start = row[6]
        #     end = row[7]
        # elif table == "CUPTI_ACTIVITY_KIND_MEMCPY2":
        #     start = row[6]
        #     end = row[7]

    heap = Heap()

    wall_start = time.time()
    rows_read = 0
    next_pct = 0
    for new_table, new_row, new_start, new_stop in db.multi_rows(tables, start_ts=begin, end_ts=end):
        rows_read += 1
        cur_pct = rows_read / total_rows * 100
        if cur_pct > next_pct:
            sys.stderr.write(
                "{}% ({}/{})\n".format(int(cur_pct), rows_read, total_rows))
            next_pct = ceil(cur_pct)
            sys.stderr.flush()

        # consume priority queue operations until we reach the start of the next operation
        # print("consuming until", new_start)
        while len(heap) and heap.peek()[0] <= new_start:
            _, (table, row, op) = heap.pop()
            consume(table, row, op)

        # push start and stop markers onto heap
        heap.push((new_table, new_row, START), new_start)
        heap.push((new_table, new_row, STOP), new_stop)

    # finish up the heap
    while len(heap):
        _, (table, row, op) = heap.pop()
        consume(table, row, op)

    if gpu_kernels.is_active():
        logger.error("At least one GPU kernel never finished!")
    print("GPU KERNELS: {}s".format(gpu_kernels.time))
