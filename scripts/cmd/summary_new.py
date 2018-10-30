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
        self.listeners = set()

    def set_idle(self, ts):
        if not self.multi_active:
            assert self.num_active == 1
        self.num_active -= 1
        if self.num_active == 0:
            self.time += (ts - self.active_start)

    def set_active(self, ts):
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

    def __or__(a, b):
        ret = CombinedTimeline()

    def prompt_listeners(self):
        for l in self.listeners:
            l.prompt()


class CombinedTimeline(object):
    def __init__(self, update_function):
        """ update function is expected to return whether the combined timeline should be active"""
        self.update_function = update_function
        self.time = 0.0
        self.actived_at = None
        self.prev_active = False

    def is_active(self):
        return self.prev_active

    def update(self, ts):
        active = self.update_function()
        if self.prev_active and not active:  # active -> idle
            self.time += (ts - self.activated_at)
        elif not self.prev_active and active:  # idle -> active
            self.activated_at = ts
        self.prev_active = active


class NestedTimeline(object):
    def __init__(self):
        self.timelines = defaultdict(lambda: Timeline())
        self.time = 0.0

    def _any_active(self):
        for _, timeline in self.timelines.items():
            if timeline.is_active():
                return True
        return False

    def _all_idle(self):
        for _, timeline in self.timelines.items():
            if timeline.is_active():
                return False
        return True

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

    IDLE = 0
    BUSY = 1
    START = 'op_start'
    STOP = 'op_stop'

    gpu_kernels = defaultdict(lambda: Timeline())  # indexed by GP
    comms = defaultdict(lambda: Timeline())  # indexed by GPU
    # driver_state = NestedTimeline()  # indexed by tid
    # runtime_states = NestedTimeline()  # indexed by tid

    any_gpu_kernel = CombinedTimeline(lambda: any(k.is_active()
                                                  for _, k in gpu_kernels.items()))

    any_comm = CombinedTimeline(lambda: any(c.is_active()
                                            for _, c in comms.items()))

    exposed_gpu = CombinedTimeline(lambda: any_gpu_kernel.is_active() and not (
        any_comm.is_active()))

    queue = []

    def consume(table, row, op):
        nonlocal any_gpu_kernel
        nonlocal gpu_kernels
        nonlocal comms
        nonlocal any_comm

        start = None
        end = None

        # if table == "CUPTI_ACTIVITY_KIND_RUNTIME":
        #     start = row[2]
        #     end = row[3]
        #     tid = row[5]
        #     if op == START:
        #         runtime_states.set_active(tid, start)
        #     else:
        #         runtime_states.set_idle(tid, end)
        # elif table == "CUPTI_ACTIVITY_KIND_DRIVER":
        #     cbid = row[1]
        #     start = row[2]
        #     end = row[3]
        #     process_id = row[4]
        #     thread_id = row[5]
        #     correlation_id = row[6]
        if table == "CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL" or table == "CUPTI_ACTIVITY_KIND_KERNEL":
            start = row[6]
            end = row[7]
            device_id = row[9]
            if op == START:
                gpu_kernels[device_id].set_active(start)
            else:
                gpu_kernels[device_id].set_idle(end)
        elif table == "CUPTI_ACTIVITY_KIND_MEMCPY":
            src_kind = row[2]
            dst_kind = row[3]
            start = row[6]
            end = row[7]
            device_id = row[8]
            if src_kind == cupti.activity_memory_kind.DEVICE:
                src_tag = 'gpu' + str(device_id)
            else:
                src_tag = 'cpu'
            if dst_kind == cupti.activity_memory_kind.DEVICE:
                dst_tag = 'gpu' + str(device_id)
            else:
                dst_tag = 'cpu'
            comm_id = src_tag + "-" + dst_tag
            if op == START:
                comms[comm_id].set_active(start)
            else:
                comms[comm_id].set_idle(end)
        # elif table == "CUPTI_ACTIVITY_KIND_MEMCPY2":
        #     start = row[6]
        #     end = row[7]

        # for now, just update combined timelines after every row, since we don't know what kind of ops each combined timeline needs
        if op == START:
            if start is not None:
                any_gpu_kernel.update(start)
                any_comm.update(start)
                exposed_gpu.update(start)
        else:
            if end is not None:
                any_gpu_kernel.update(end)
                any_comm.update(end)
                exposed_gpu.update(end)

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

    print("GPU KERNELS:         {}s".format(any_gpu_kernel.time/1e9))
    for gpu, timeline in gpu_kernels.items():
        print("GPU {}: {}s".format(gpu, timeline.time/1e9))
    print("EXPOSED GPU KERNELS: {}s".format(exposed_gpu.time/1e9))
