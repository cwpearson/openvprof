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
import timeline
import operator
from functools import reduce

import cupti.activity_memory_kind
import cupti.activity
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

    first_timestamp = db.get_first_start()
    logger.debug("First timestamp: {}".format(first_timestamp))

    if end:
        logger.debug("got --end = {}".format(end))
        if end[-1] == "s":
            end = first_timestamp + float(end[:-1]) * 1_000_000_000
        end = int(end)
        logger.debug("converted --end to ts {}".format(end))
    if begin:
        logger.debug("got --begin = {}".format(begin))
        if begin[-1] == "s":
            begin = first_timestamp + float(begin[:-1]) * 1_000_000_000
        begin = int(begin)
        logger.debug("converted --begin to ts {}".format(begin))
    else:
        logger.debug("using first timestamp in file as begin")
        begin = first_timestamp

    def normalize_to_nvprof(ts):
        """ normalize all timestamps to the beginning of our analysis"""
        adjusted = ts - first_timestamp
        # assert adjusted >= 0
        return adjusted

    def normalize_to_begin(ts):
        adjusted = ts - begin
        return adjusted

    logger.debug("Loading devices")
    devices = db.get_devices()
    logger.debug("{} devices".format(len(devices)))

    logger.debug("Loading strings")
    nvprof_id_to_string, nvprof_string_to_id = db.get_strings()
    logger.debug("{} strings".format(len(nvprof_id_to_string)))

    logger.debug("Loading thread ids")
    tids = set()
    for row in db.execute("SELECT distinct threadId from CUPTI_ACTIVITY_KIND_RUNTIME"):
        tid = row[0]
        if tid < 0:
            tid += 2**32
            assert tid >= 0
        tids.add(tid)
    logger.debug("{} thread IDs".format(len(tids)))
    pids = set()
    for row in db.execute("SELECT distinct processId from CUPTI_ACTIVITY_KIND_RUNTIME"):
        pids.add(row[0])
    logger.debug("{} process IDs".format(len(pids)))

    tables = [
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL',
        'CUPTI_ACTIVITY_KIND_MEMCPY',
        # 'CUPTI_ACTIVITY_KIND_MEMCPY2',
        'CUPTI_ACTIVITY_KIND_KERNEL',
        'CUPTI_ACTIVITY_KIND_RUNTIME',
    ]

    total_rows = 0
    for table in tables:
        total_rows += db.num_rows(table, ranges=[[begin, end]])
    logger.debug("{} rows".format(total_rows))

    START = 'op_start'
    STOP = 'op_stop'

    gpu_kernels = {}
    runtimes = {}
    comms = {}
    for d in devices:
        gpu_kernels[d.id_] = timeline.Timeline()
        comms["cpu-gpu" + str(d.id_)] = timeline.Timeline()
        comms["gpu" + str(d.id_) + "-cpu"] = timeline.Timeline()

        for d1 in devices:
            comms["gpu" + str(d.id_) + "-gpu" + str(d1.id_)
                  ] = timeline.Timeline()

    for p in pids:
        for t in tids:
            runtimes[t] = timeline.Timeline()

    any_gpu_kernel = reduce(
        operator.or_, gpu_kernels.values(), timeline.NeverActive())

    any_comm = reduce(
        operator.or_, comms.values(), timeline.NeverActive())

    any_runtime = reduce(
        operator.or_, runtimes.values(), timeline.NeverActive())

    exposed_gpu = any_gpu_kernel & (~ (any_comm | any_runtime))
    exposed_comm = any_comm & (~ (any_gpu_kernel | any_runtime))
    exposed_runtime_mask = ~ (any_gpu_kernel | any_comm)
    exposed_runtime = any_runtime & exposed_runtime_mask

    any_runtime.verbose = True
    any_runtime.name = "any_runtime"
    any_gpu_kernel.verbose = True
    any_gpu_kernel.name = "any_gpu_kernel"
    # any_comm.verbose = True
    any_comm.name = "any_comm"
    exposed_runtime.verbose = True
    exposed_runtime.name = "exposed_runtime"
    exposed_runtime_mask.verbose = True
    exposed_runtime_mask.name = "exposed_runtime_mask"
    queue = []

    def consume(ts, table, row, op):

        start = None
        end = None
        ts = normalize_to_nvprof(ts)

        record = None

        if table == "CUPTI_ACTIVITY_KIND_RUNTIME":
            # print("consuming runtime", op)
            cbid, start, end, pid, tid = row[1:6]
            start = normalize_to_nvprof(start)
            end = normalize_to_nvprof(end)
            if tid < 0:
                tid += 2**32
            record = cupti.activity.Runtime(cbid, pid, tid)
            if op == START:
                runtimes[tid].set_active(start)
            else:
                runtimes[tid].set_idle(end)
        elif table == "CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL" or table == "CUPTI_ACTIVITY_KIND_KERNEL":
            # print("consuming GPU kernel", op)
            start = row[6]
            end = row[7]
            start = normalize_to_nvprof(start)
            end = normalize_to_nvprof(end)
            device_id = row[9]
            record = None
            # print(start, end, device_id, op)
            if op == START:
                gpu_kernels[device_id].set_active(start)
            else:
                gpu_kernels[device_id].set_idle(end)
            # assert False
        elif table == "CUPTI_ACTIVITY_KIND_MEMCPY":
            src_kind = row[2]
            dst_kind = row[3]
            start = row[6]
            end = row[7]
            start = normalize_to_nvprof(start)
            end = normalize_to_nvprof(end)
            device_id = row[8]
            record = None
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

        if op == START:
            if isinstance(record, cupti.activity.Runtime):
                any_runtime.start_record_if_active(ts, record)
                exposed_runtime.start_record_if_active(ts, record)
            elif isinstance(record, cupti.activity.Comm):
                exposed_communication.start_record_if_active(ts, record)
        if op == STOP:
            if isinstance(record, cupti.activity.Runtime):
                any_runtime.end_record(ts, record)
                exposed_runtime.end_record(ts, record)
            elif isinstance(record, cupti.activity.Comm):
                exposed_communication.end_record(ts, record)

    heap = Heap()

    loop_wall_start = None
    rows_read = 0
    next_pct = 1
    progress_start = None
    last_record_end = 0
    first_record_start = None
    for new_table, new_row, new_start, new_stop in db.multi_rows(tables, start_ts=begin, end_ts=end):
        # print("read", new_table, "at",
        #       normalize_to_nvprof(new_start) / 1e9,
        #       normalize_to_nvprof(new_stop) / 1e9)
        # if new_stop:
        #     assert new_stop <= end
        if not loop_wall_start:
            loop_wall_start = time.time()
        if not progress_start:
            progress_start = new_start
        if not first_record_start:
            first_record_start = new_start
        first_record_start = min(first_record_start, new_start)
        last_record_end = max(last_record_end, new_stop)

        rows_read += 1
        cur_pct = int(rows_read / total_rows * 100)
        if cur_pct >= next_pct:
            avg_rows_per_sec = rows_read / (time.time() - loop_wall_start)
            eta = (total_rows - rows_read) / avg_rows_per_sec
            sys.stderr.write(
                "{}% ({}/{} rows) ({}ns-{}ns) ({} rows/s) (eta {}s)\n".format(int(cur_pct), rows_read,
                                                                              total_rows, progress_start, new_stop, int(avg_rows_per_sec), int(eta)))
            next_pct = cur_pct + 1
            sys.stderr.flush()
            progress_start = new_start

        # consume priority queue operations until we reach the start of the next operation
        # print("consuming until", new_start)
        while len(heap) and heap.peek()[0] <= new_start:
            ts, (table, row, op) = heap.pop()
            consume(ts, table, row, op)

        # push start and stop markers onto heap
        heap.push((new_table, new_row, START), new_start)
        heap.push((new_table, new_row, STOP), new_stop)

    # finish up the heap
    while len(heap):
        ts, (table, row, op) = heap.pop()
        consume(ts, table, row, op)

    print("Records cover: {}s".format(
        (last_record_end - first_record_start) / 1e9))

    print("Communication Report")
    print("====================")
    print("Any communication active: {}s".format(any_comm.time/1e9))
    print("Any communication breakdown")
    print("---------------------------")
    for tag, t in comms.items():
        print("  {} Communication Time: {}s".format(tag, t.time/1e9))
    print("Total Exposed Communication Time: {}s".format(exposed_comm.time/1e9))
    print("Exposed communication breakdown")
    print("-------------------------------")

    print("Runtime Report")
    print("==============")
    print("Total Exposed Runtime Time: {}s".format(exposed_runtime.time/1e9))

    print("Exposed Runtime Breakdown:")
    print("------------------------------------")
    runtime_times = sorted(
        list(exposed_runtime.record_times.items()), key=lambda t: t[1], reverse=True)
    for record, elapsed in runtime_times:
        print("  {} {}s".format(str(record), elapsed / 1e9))
    print("Any Runtime Active: {}s".format(any_runtime.time/1e9))
    print("Breakdown")
    print("------------------------")
    runtime_times = sorted(
        list(any_runtime.record_times.items()), key=lambda t: t[1], reverse=True)
    for record, elapsed in runtime_times:
        print("  {} {}s".format(str(record), elapsed / 1e9))

    print("Kernel Report")
    print("=============")
    print("Total Exposed GPU Kernel Time: {}s".format(exposed_gpu.time/1e9))
    print("Any Kernel Active: {}s".format(any_gpu_kernel.time/1e9))
    for gpu, t in gpu_kernels.items():
        print("GPU {} Kernel Time: {}s".format(gpu, t.time/1e9))
