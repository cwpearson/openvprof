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
import nvprof.record
from nvprof.db import Db

logger = logging.getLogger(__name__)


@click.command()
@click.argument('filename')
@click.option('-b', '--begin', help='Only consider events that begin after this time')
@click.option('-e', '--end', help='Only consider records that end before this time')
@click.option('-r', '--range', multiple=True, help='Only consider records that occur during marker ranges with this in the name')
@click.option('-n', '--first-ranges', help='Only consider the first n ranges, ordered by start time', type=int)
@click.pass_context
def summary(ctx, filename, begin, end, range, first_ranges):

    db = Db(filename)

    nvprof_start_timestamp, _ = db.get_extent()
    logger.debug("First timestamp: {}".format(nvprof_start_timestamp))

    if end:
        logger.debug("got --end = {}".format(end))
        if end[-1] == "s":
            end = nvprof_start_timestamp + float(end[:-1]) * 1_000_000_000
        end = int(end)
        logger.debug("converted --end to ts {}".format(end))
    if begin:
        logger.debug("got --begin = {}".format(begin))
        if begin[-1] == "s":
            begin = nvprof_start_timestamp + float(begin[:-1]) * 1_000_000_000
        begin = int(begin)
        logger.debug("converted --begin to ts {}".format(begin))

    if begin or end:
        opt_spans = [(begin, end)]
    else:
        opt_spans = []

    def normalize_to_nvprof(ts):
        """ normalize all timestamps to the beginning of our analysis"""
        adjusted = ts - nvprof_start_timestamp
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
    logger.debug("{} distinct thread IDs".format(len(tids)))
    pids = set()
    for row in db.execute("SELECT distinct processId from CUPTI_ACTIVITY_KIND_RUNTIME"):
        pids.add(row[0])
    logger.debug("{} distinct process IDs".format(len(pids)))

    selected_timeslices = 0.0
    if range:
        ranges_view = db.ranges_with_name(range, first_n=first_ranges)
        num_ranges = db.execute(
            'SELECT Count(*) from {}'.format(ranges_view)).fetchone()[0]
        logger.debug("{} ranges match the names {}".format(num_ranges, range))

        # figure out how much of the time is spent during the selected ranges
        range_edges = db.edges_from_rows(ranges_view)
        num_overlapped = 0
        in_range = None
        for row in db.ordered_edges(range_edges):
            ts = row[0]
            is_posedge = row[1]
            row = row[2:]
            if is_posedge:
                num_overlapped += 1
            else:
                num_overlapped -= 1
            if num_overlapped == 1:
                in_range = ts
            elif num_overlapped == 0:
                selected_timeslices += ts - in_range
                in_range = None
    logger.debug("Selected timeslices cover {}s".format(
        selected_timeslices/1e9))

    tables = [
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL',
        'CUPTI_ACTIVITY_KIND_MEMCPY',
        'CUPTI_ACTIVITY_KIND_KERNEL',
        'CUPTI_ACTIVITY_KIND_RUNTIME',
    ]

    # make filtered versions of all the tables
    filtered_edges = {}
    total_edges = 0
    for table in tables:
        filtered = db.create_filtered_table(
            table, range_names=range, first_n_ranges=first_ranges, spans=opt_spans)

        num_rows = db.execute(
            'SELECT Count(*) from {}'.format(filtered)).fetchone()[0]
        logger.debug("{} rows in {} overlap ranges {}".format(
            num_rows, table, range))

        edges_view = db.create_edges_view(filtered)
        logger.debug("{} filtered is {}, edges in {}".format(
            table, filtered, edges_view))
        # sql = db._rows_in_range_name(table, range)
        num_rows = db.execute(
            'SELECT Count(*) from {}'.format(edges_view)).fetchone()[0]
        logger.debug("{} edges in {} overlap ranges {}".format(
            num_rows, table, range))
        total_edges += num_rows
        filtered_edges[table] = edges_view

    for table, edges in filtered_edges.items():
        logger.debug('{} -> {}'.format(table, edges))

    logger.debug("{} edges".format(total_edges))

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
    any_gpu_kernel.record_key = lambda r: (r.device_id, r.name)
    exposed_gpu.record_key = lambda r: (r.device_id, r.name)
    exposed_comm = any_comm & (~ (any_gpu_kernel | any_runtime))
    exposed_runtime_mask = ~ (any_gpu_kernel | any_comm)
    exposed_runtime = any_runtime & exposed_runtime_mask
    exposed_runtime.record_key = lambda r: (r.pid, r.tid, r.name())
    any_runtime.record_key = lambda r: (r.pid, r.tid, r.name())

    # any_runtime.verbose = True
    any_runtime.name = "any_runtime"
    # any_gpu_kernel.verbose = True
    any_gpu_kernel.name = "any_gpu_kernel"
    # any_comm.verbose = True
    any_comm.name = "any_comm"
    # exposed_runtime.verbose = True
    exposed_runtime.name = "exposed_runtime"
    # exposed_runtime_mask.verbose = True
    exposed_runtime_mask.name = "exposed_runtime_mask"

    edges_read = 0
    loop_wall_start = time.time()
    # for a particular table, how to create a row
    row_factories = {}
    for table, edges in filtered_edges.items():
        if table == 'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL':
            row_factories[edges] = nvprof.record.ConcurrentKernel.from_nvprof_row
        elif table == 'CUPTI_ACTIVITY_KIND_MEMCPY':
            row_factories[edges] = nvprof.record.Memcpy.from_nvprof_row
        elif table == 'CUPTI_ACTIVITY_KIND_RUNTIME':
            row_factories[edges] = nvprof.record.Runtime.from_nvprof_row
        elif table == 'CUPTI_ACTIVITY_KIND_RANGE':
            row_factories[edges] = nvprof.record.Range.from_nvprof_row
    for timestamp, is_posedge, record in db.multi_ordered_edges_records(filtered_edges.values(), row_factories=row_factories):

        edges_read += 1
        if edges_read % 15000 == 0:
            elapsed = time.time() - loop_wall_start
            logger.debug("{} rows/sec, {}/{} ({}%)".format(edges_read /
                                                           elapsed, edges_read, total_edges, edges_read/total_edges * 100))

        assert timestamp
        assert record
        timestamp = normalize_to_nvprof(timestamp)

        # Update active masks
        if isinstance(record, nvprof.record.Runtime):
            if is_posedge:
                runtimes[record.tid].set_active(timestamp)
            else:
                runtimes[record.tid].set_idle(timestamp)
        elif isinstance(record, nvprof.record.ConcurrentKernel):
            if is_posedge:
                gpu_kernels[record.device_id].set_active(timestamp)
            else:
                gpu_kernels[record.device_id].set_idle(timestamp)
        elif isinstance(record, nvprof.record.Memcpy):
            if record.src_kind == cupti.activity_memory_kind.DEVICE:
                src_tag = 'gpu' + str(record.device_id)
            else:
                src_tag = 'cpu'
            if record.dst_kind == cupti.activity_memory_kind.DEVICE:
                dst_tag = 'gpu' + str(record.device_id)
            else:
                dst_tag = 'cpu'
            comm_id = src_tag + "-" + dst_tag
            if is_posedge:
                comms[comm_id].set_active(timestamp)
            else:
                comms[comm_id].set_idle(timestamp)

        # Track records by various activity masks

        if is_posedge:
            if isinstance(record, nvprof.record.Comm):
                exposed_communication.start_record_if_active(
                    timestamp, record)
        else:
            if isinstance(record, nvprof.record.Comm):
                exposed_communication.end_record(timestamp, record)

        if isinstance(record, nvprof.record.Runtime):
            if is_posedge:
                assert any_runtime.evaluate()
                any_runtime.start_record_if_active(timestamp, record)
                exposed_runtime.start_record_if_active(timestamp, record)
            else:
                any_runtime.end_record(timestamp, record)
                exposed_runtime.end_record(timestamp, record)

        elif isinstance(record, nvprof.record.ConcurrentKernel):
            if is_posedge:
                any_gpu_kernel.start_record_if_active(timestamp, record)
            else:
                any_gpu_kernel.end_record(timestamp, record)

    print("Selected timeslices cover {}s".format(selected_timeslices/1e9))

    print("Marker Report")
    print("=============")
    print("<not implemented>")
    print()

    print("Communication Report")
    print("====================")
    print("Active communication Time-Slices: {}s".format(any_comm.time/1e9))
    print("Exposed communication Time-Slices: {}s".format(exposed_comm.time/1e9))
    print("Active Communication Time-Slices")
    print("--------------------------------")
    for tag, t in comms.items():
        print("  {} {}s".format(tag, t.time/1e9))

    print("Exposed communication breakdown")
    print("-------------------------------")
    print("<not implemented>")
    print("")

    print("Runtime Report")
    print("==============")
    print("Any CUDA Runtime Time-Slices: {}s".format(any_runtime.time/1e9))
    print("Exposed CUDA Runtime Time-Slices: {}s".format(exposed_runtime.time/1e9))

    print("Exposed Runtime by Thread")
    print("-------------------------")
    thread_times = defaultdict(lambda: 0.0)
    for record, elapsed in exposed_runtime.record_times.items():
        thread_times[record[1]] += elapsed
    thread_times = sorted(thread_times.items(),
                          key=lambda t: t[1], reverse=True)
    for name, elapsed in thread_times:
        print("  {} {}s".format(name, elapsed/1e9))

    print("Exposed Runtime by Call")
    print("-----------------------")
    call_times = defaultdict(lambda: 0.0)
    for record, elapsed in exposed_runtime.record_times.items():
        call_times[record[2]] += elapsed
    call_times = sorted(call_times.items(), key=lambda t: t[1], reverse=True)
    for name, elapsed in call_times:
        print("  {} {}s".format(name, elapsed/1e9))

    print("Exposed Runtime Breakdown")
    print("-------------------------")
    runtime_times = sorted(
        list(exposed_runtime.record_times.items()), key=lambda t: t[1], reverse=True)
    for record, elapsed in runtime_times:
        print("  {} {}s".format(str(record), elapsed / 1e9))

    print("Any Runtime Breakdown")
    print("---------------------")
    runtime_times = sorted(
        list(any_runtime.record_times.items()), key=lambda t: t[1], reverse=True)
    for record, elapsed in runtime_times:
        print("  {} {}s".format(str(record), elapsed / 1e9))

    print("Kernel Report")
    print("=============")
    print("Any GPU Kernel Time-Slices: {}s".format(any_gpu_kernel.time/1e9))
    print("Exposed GPU Kernel Time-Slices: {}s".format(exposed_gpu.time/1e9))

    print("Active kernel time-slices by GPU")
    print("--------------------------------")
    for gpu, t in gpu_kernels.items():
        print("  GPU {} Kernel Time: {}s".format(gpu, t.time/1e9))

    gpu_kernel_names = defaultdict(
        lambda: defaultdict(lambda: 0.0))  # [gpu][name] = 0.0
    for r, elapsed in any_gpu_kernel.record_times.items():
        gpu_kernel_names[r[0]][r[1]] += elapsed

    for gpu, d in gpu_kernel_names.items():
        print("Active kernel time-slices on GPU {}".format(gpu))
        print("-----------------------------------")
        kernel_times = sorted(list(d.items()),
                              key=lambda t: t[1], reverse=True)
        for name, elapsed in kernel_times:
            print("  {} {}s".format(name, elapsed/1e9))
