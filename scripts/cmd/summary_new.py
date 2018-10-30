import click
import copy
import sqlite3
import logging
import sys
import time
from math import ceil
from collections import defaultdict
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


@click.command()
@click.argument('filename')
@click.pass_context
def summary_new(ctx, filename):

    db = Db(filename)

    logger.debug("Loading strings")
    nvprof_id_to_string, nvprof_string_to_id = db.get_strings()

    tables = [
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL',
        'CUPTI_ACTIVITY_KIND_MEMCPY',
        'CUPTI_ACTIVITY_KIND_MEMCPY2',
        'CUPTI_ACTIVITY_KIND_KERNEL',
        'CUPTI_ACTIVITY_KIND_DRIVER',
        'CUPTI_ACTIVITY_KIND_RUNTIME'
    ]

    iter_column = 'start'

    total_runtime = 0
    total_driver = 0
    total_kernel = 0
    total_memcpy = 0

    IDLE = 0
    BUSY = 1
    START = 'op_start'
    STOP = 'op_stop'

    gpu_states = defaultdict(lambda: (0, IDLE))
    comm_states = defaultdict(lambda: (0, IDLE))
    driver_state = (0, IDLE)
    runtime_states = defaultdict(lambda: (0, IDLE))  # indexed by tid

    queue = []

    def consume(table, row, op):
        nonlocal total_runtime
        nonlocal total_driver
        nonlocal total_kernel
        nonlocal total_memcpy
        nonlocal runtime_states

        if table == "CUPTI_ACTIVITY_KIND_RUNTIME":
            start = row[2]
            end = row[3]
            tid = row[5]
            if op == START:
                assert runtime_states[tid][1] == IDLE
                runtime_states[tid] = (start, BUSY)
            else:
                start, prev_state = runtime_states[tid]
                assert prev_state == BUSY
                runtime_states[tid] = (end, IDLE)
                total_runtime += (end - start)
        elif table == "CUPTI_ACTIVITY_KIND_DRIVER":
            start = row[2]
            end = row[3]
            #total_driver += (end - start)
        elif table == "CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL" or table == "CUPTI_ACTIVITY_KIND_KERNEL":
            start = row[6]
            end = row[7]
            #total_kernel += (end - start)
        elif table == "CUPTI_ACTIVITY_KIND_MEMCPY":
            start = row[6]
            end = row[7]
            #total_memcpy += (end - start)
        elif table == "CUPTI_ACTIVITY_KIND_MEMCPY2":
            start = row[6]
            end = row[7]
            #total_memcpty += (end - start)

    heap = Heap()

    wall_start = time.time()
    rows_read = 0
    for new_table, new_row, new_start, new_stop in db.multi_rows(tables):

        # consume priority queue operations until we reach the start of the next operation
        # print("consuming until", new_start)
        while len(heap) and heap.peek()[0] <= new_start:
            _, (table, row, op) = heap.pop()
            #print("consuming", table, row, op)
            consume(table, row, op)

        # push start and stop markers onto heap
        #print("pushing start")
        heap.push((new_table, new_row, START), new_start)
        #print("pushing stop")
        heap.push((new_table, new_row, STOP), new_stop)

    # finish up the heap
    while len(heap):
        _, (table, row, op) = heap.pop()
        consume(table, row, op)

    print("runtime: {}s".format(total_runtime/1e9))
    print("driver:  {}s".format(total_driver/1e9))
    print("kernel: {}s".format(total_kernel/1e9))
    print("memcpy: {}s".format(total_memcpy/1e9))
