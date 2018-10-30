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

    def __init__(self):
        self.num_active = 0
        self.time = 0.0
        self.active_start = None

    def set_idle(self, ts):
        self.num_active -= 1
        assert self.num_active >= 0
        if self.num_active == 0:
            self.time += (ts - self.active_start)

    def set_active(self, ts):
        if self.num_active == 0:
            self.active_start = ts
        self.num_active += 1

    def is_active(self):
        return self.num_active > 0


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


@click.command()
@click.argument('filename')
@click.option('-b', '--begin', help='Only consider events that begin after this time')
@click.option('-e', '--end', help='Only consider records that end before this time')
@click.pass_context
def summary_new(ctx, filename, begin, end):

    db = Db(filename)

    logger.debug("Loading devices")
    devices = db.get_devices()
    logger.debug("{} devices".format(len(devices)))

    logger.debug("Loading strings")
    nvprof_id_to_string, nvprof_string_to_id = db.get_strings()
    logger.debug("{} strings".format(len(nvprof_id_to_string)))

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

    START = 'op_start'
    STOP = 'op_stop'

    gpu_kernels = {}
    comms = {}
    for d in devices:
        gpu_kernels[d.id_] = Timeline()
        comms[d.id_] = Timeline()
    runtimes = defaultdict(lambda: Timeline())  # indexed by tid

    any_gpu_kernel = CombinedTimeline(lambda: any(k.is_active()
                                                  for _, k in gpu_kernels.items()))

    any_comm = CombinedTimeline(lambda: any(c.is_active()
                                            for _, c in comms.items()))

    any_runtime = CombinedTimeline(lambda: any(r.is_active()
                                               for _, r in runtimes.items()))

    exposed_gpu = CombinedTimeline(lambda: any_gpu_kernel.is_active() and not (
        any_comm.is_active() or any_runtime.is_active()))

    exposed_comm = CombinedTimeline(lambda: any_comm.is_active() and not (
        any_gpu.is_active() or any_runtime.is_active()))

    queue = []

    def consume(table, row, op):

        start = None
        end = None

        if table == "CUPTI_ACTIVITY_KIND_RUNTIME":
            start = row[2]
            end = row[3]
            tid = row[5]
            if op == START:
                runtimes[tid].set_active(start)
            else:
                runtimes[tid].set_idle(end)
        # elif table == "CUPTI_ACTIVITY_KIND_DRIVER":
        #     cbid = row[1]
        #     start = row[2]
        #     end = row[3]
        #     process_id = row[4]
        #     thread_id = row[5]
        #     correlation_id = row[6]
        elif table == "CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL" or table == "CUPTI_ACTIVITY_KIND_KERNEL":
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
                any_runtime.update(start)
                exposed_gpu.update(start)
                exposed_comm.update(start)
        else:
            if end is not None:
                any_gpu_kernel.update(end)
                any_comm.update(end)
                any_runtime.update(end)
                exposed_gpu.update(end)
                exposed_comm.update(end)

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

    print("Total Kernel Time: {}s".format(any_gpu_kernel.time/1e9))
    for gpu, timeline in gpu_kernels.items():
        print("GPU {} Kernel Time: {}s".format(gpu, timeline.time/1e9))
    print("Total CUDA Runtime: {}s".format(any_runtime.time/1e9))
    for tid, timeline in runtimes.items():
        print("Thread {} Runtime: {}s".format(tid, timeline.time/1e9))
    print("Total Communication Time: {}s".format(any_comm.time/1e9))
    for tag, timeline in comms.items():
        print("{} Communication Time: {}s".format(tag, timeline.time/1e9))
    print("Total Exposed GPU Kernel Time: {}s".format(exposed_gpu.time/1e9))
    print("Total Exposed Communication Time: {}s".format(exposed_comm.time/1e9))
