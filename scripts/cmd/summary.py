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

    logger.info("Loading devices")
    devices = db.get_devices()
    logger.info("{} devices".format(len(devices)))

    logger.info("Loading strings")
    nvprof_id_to_string, nvprof_string_to_id = db.get_strings()
    logger.info("{} strings".format(len(nvprof_id_to_string)))

    logger.info("Loading thread ids")
    tids = set()
    for row in db.execute("SELECT distinct threadId from CUPTI_ACTIVITY_KIND_RUNTIME"):
        tid = row[0]
        if tid < 0:
            tid += 2**32
            assert tid >= 0
        tids.add(tid)
    logger.info("{} distinct thread IDs".format(len(tids)))
    pids = set()
    for row in db.execute("SELECT distinct processId from CUPTI_ACTIVITY_KIND_RUNTIME"):
        pids.add(row[0])
    logger.info("{} distinct process IDs".format(len(pids)))

    selected_timeslices = 0.0
    if range:
        ranges_view = db.ranges_with_name(range, first_n=first_ranges)
        num_ranges = db.execute(
            'SELECT Count(*) from {}'.format(ranges_view)).fetchone()[0]
        logger.info("{} ranges match the names {}".format(num_ranges, range))

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
    logger.info("Selected timeslices cover {}s".format(
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

    gpu_kernel_masks = {}
    runtime_masks = {}
    comm_masks = {}
    for d in devices:
        gpu_kernel_masks[d.id_] = timeline.Timeline()
        comm_masks["cpu-gpu" + str(d.id_)] = timeline.Timeline()
        comm_masks["gpu" + str(d.id_) + "-cpu"] = timeline.Timeline()

        for d1 in devices:
            comm_masks["gpu" + str(d.id_) + "-gpu" + str(d1.id_)
                       ] = timeline.Timeline()

    for p in pids:
        for t in tids:
            runtime_masks[t] = timeline.Timeline()

    # define combined activity masks
    any_gpu_kernel_mask = reduce(
        operator.or_, gpu_kernel_masks.values(), timeline.NeverActive())

    any_comm_mask = reduce(
        operator.or_, comm_masks.values(), timeline.NeverActive())

    any_runtime_mask = reduce(
        operator.or_, runtime_masks.values(), timeline.NeverActive())

    exposed_gpu_kernel_mask = any_gpu_kernel_mask & (
        ~ (any_comm_mask | any_runtime_mask))

    exposed_comm_mask = any_comm_mask & (
        ~ (any_gpu_kernel_mask | any_runtime_mask))
    exposed_runtime_mask = any_runtime_mask & ~ (
        any_gpu_kernel_mask | any_comm_mask)

    # define record trackers
    any_gpu_kernel_records = timeline.Records(
        mask=any_gpu_kernel_mask,
        key_func=lambda r: (r.device_id, r.name),
    )

    exposed_gpu_kernel_records = timeline.Records(
        mask=exposed_gpu_kernel_mask,
        key_func=lambda r: (r.device_id, r.name),
    )

    exposed_runtime_records = timeline.Records(
        mask=exposed_runtime_mask,
        key_func=lambda r: (r.pid, r.tid, r.name()),
    )

    any_runtime_records = timeline.Records(
        mask=any_runtime_mask,
        key_func=lambda r: (r.pid, r.tid, r.name()),
    )

    exposed_comm_records = timeline.Records(
        mask=exposed_comm_mask,
    )

    edges_read = 0
    loop_wall_start = time.time()
    # for a particular table, how to create a row
    row_factories = {}
    for table, edges in filtered_edges.items():
        if table == 'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL':
            row_factories[edges] = nvprof.record.ConcurrentKernel.from_nvprof_row
        elif table == 'CUPTI_ACTIVITY_KIND_MEMCPY':
            row_factories[edges] = nvprof.record.Comm.from_nvprof_memcpy_row
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

        # FIXME: need to ignore the case when communication is overlapped with its corresponding runtime call
        # could create some special runtime masks to handle communication activity

        # Update active masks
        if isinstance(record, nvprof.record.Runtime):
            # ignore cudaEventSynchonize, cudaDeviceSynchronize, and cudaStreamSynchronize
            # by definition, these functions block while waiting for the other kinds of activity

            if record.name() == "cudaEventSynchronize":
                continue
            elif record.name() == "cudaStreamSynchronize":
                continue
            elif record.name() == "cudaDeviceSynchronize":
                continue

            if is_posedge:
                runtime_masks[record.tid].set_active(timestamp)
                any_runtime_records.start_record(timestamp, record)
                exposed_runtime_records.start_record(timestamp, record)
            else:
                runtime_masks[record.tid].set_idle(timestamp)
                any_runtime_records.end_record(timestamp, record)
                exposed_runtime_records.end_record(timestamp, record)
        elif isinstance(record, nvprof.record.ConcurrentKernel):
            if is_posedge:
                gpu_kernel_masks[record.device_id].set_active(timestamp)
                any_gpu_kernel_records.start_record(timestamp, record)
            else:
                gpu_kernel_masks[record.device_id].set_idle(timestamp)
                any_gpu_kernel_records.end_record(timestamp, record)
        elif isinstance(record, nvprof.record.Comm):
            if record.src_id == -1:
                src_tag = 'cpu'
            else:
                src_tag = 'gpu' + str(record.src_id)
            if record.dst_id == -1:
                dst_tag = 'cpu'
            else:
                dst_tag = 'gpu' + str(record.dst_id)
            comm_id = src_tag + "-" + dst_tag
            if is_posedge:
                comm_masks[comm_id].set_active(timestamp)
                exposed_comm_records.start_record(
                    timestamp, record)
            else:
                comm_masks[comm_id].set_idle(timestamp)
                exposed_comm_records.end_record(timestamp, record)

    print("Selected timeslices cover {}s".format(selected_timeslices/1e9))

    print("Marker Report")
    print("=============")
    print("<not implemented>")
    print()

    print("Communication Report")
    print("====================")
    print("Active communication Time-Slices: {}s".format(any_comm_mask.time/1e9))
    print("Exposed communication Time-Slices: {}s".format(exposed_comm_mask.time/1e9))
    print("Active Communication Time-Slices")
    print("--------------------------------")
    for tag, t in comm_masks.items():
        print("  {} {}s".format(tag, t.time/1e9))

    print("Exposed communication breakdown")
    print("-------------------------------")
    # for tag, t in exposed_comm.record_times.items():
    #     print("  {}s".format(tag))
    # print("")

    print("Runtime Report")
    print("==============")
    print("Any CUDA Runtime Time-Slices: {}s".format(any_runtime_mask.time/1e9))
    print("Exposed CUDA Runtime Time-Slices: {}s".format(exposed_runtime_mask.time/1e9))

    print("Exposed Runtime by Thread")
    print("-------------------------")
    thread_times = defaultdict(lambda: 0.0)
    for record, elapsed in exposed_runtime_records.record_times.items():
        thread_times[record[1]] += elapsed
    thread_times = sorted(thread_times.items(),
                          key=lambda t: t[1], reverse=True)
    for name, elapsed in thread_times:
        print("  {} {}s".format(name, elapsed/1e9))

    print("Any Runtime by Call")
    print("-----------------------")
    call_times = defaultdict(lambda: 0.0)
    for record, elapsed in any_runtime_records.record_times.items():
        call_times[record[2]] += elapsed
    call_times = sorted(call_times.items(), key=lambda t: t[1], reverse=True)
    for name, elapsed in call_times:
        print("  {} {}s".format(name, elapsed/1e9))

    print("Exposed Runtime by Call")
    print("-----------------------")
    call_times = defaultdict(lambda: 0.0)
    for record, elapsed in exposed_runtime_records.record_times.items():
        call_times[record[2]] += elapsed
    call_times = sorted(call_times.items(), key=lambda t: t[1], reverse=True)
    for name, elapsed in call_times:
        print("  {} {}s".format(name, elapsed/1e9))

    print("Exposed Runtime Breakdown")
    print("-------------------------")
    runtime_times = sorted(
        list(exposed_runtime_records.record_times.items()), key=lambda t: t[1], reverse=True)
    for record, elapsed in runtime_times:
        print("  {} {}s".format(str(record), elapsed / 1e9))

    print("Any Runtime Breakdown")
    print("---------------------")
    runtime_times = sorted(
        list(any_runtime_records.record_times.items()), key=lambda t: t[1], reverse=True)
    for record, elapsed in runtime_times:
        print("  {} {}s".format(str(record), elapsed / 1e9))

    print("Kernel Report")
    print("=============")
    print("Any GPU Kernel Time-Slices: {}s".format(any_gpu_kernel_mask.time/1e9))
    print("Exposed GPU Kernel Time-Slices: {}s".format(exposed_gpu_kernel_mask.time/1e9))

    print("Active kernel time-slices by GPU")
    print("--------------------------------")
    for gpu, t in gpu_kernel_masks.items():
        print("  GPU {} Kernel Time: {}s".format(gpu, t.time/1e9))

    gpu_kernel_names = defaultdict(
        lambda: defaultdict(lambda: 0.0))  # [gpu][name] = 0.0
    for r, elapsed in any_gpu_kernel_records.record_times.items():
        gpu_kernel_names[r[0]][r[1]] += elapsed

    for gpu, d in gpu_kernel_names.items():
        print("Active kernel time-slices on GPU {}".format(gpu))
        print("-----------------------------------")
        kernel_times = sorted(list(d.items()),
                              key=lambda t: t[1], reverse=True)
        for name, elapsed in kernel_times:
            print("  {} {}s".format(name, elapsed/1e9))
