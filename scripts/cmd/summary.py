import click
import sqlite3
import logging
import sys

import cupti.activity_memory_kind

logger = logging.getLogger(__name__)


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='{0}'".format(table_name))
    row = cursor.fetchone()
    if row:
        return True
    return False


def min_max_element(cursor, table_name, column_name):
    cursor.execute('SELECT Min({0}), Max({0}) from {1}'.format(
        column_name, table_name))
    row = cursor.fetchone()
    return row[0], row[1]


def table_time_extent(cursor, table_name):
    cursor.execute('SELECT Min({0}), Max({0}), Min({1}), Max({1}) from {2}'.format(
        'start', 'end', table_name))
    row = cursor.fetchone()
    begin = min(row[0], row[2]) if row[0] and row[2] else None
    end = min(row[1], row[3]) if row[1] and row[3] else None
    return begin, end


class Segments(object):
    def __init__(self, num_segments):
        self.segments = [0.0 for i in range(num_segments)]
        self.segment_counts = [0 for i in range(len(self.segments))]

    def zero(self):
        z = Segments()
        return z

    def one(self):
        o = Segments()
        o.segments = [1.0 for e in z.segments]
        return o

    def __or__(a, b):
        raise NotImplementedError

    def add_coverage(self, segment_id, coverage):
        assert segment_id >= 0
        assert segment_id < len(self.segments)

        assert coverage >= 0.0
        assert coverage <= 1.0

        current_coverage = self.segments[segment_id]
        assert current_coverage >= 0.0
        assert current_coverage <= 1.0

        new_coverage = (1 - (1 - current_coverage) * (1 - coverage))
        self.segments[segment_id] = new_coverage
        self.segment_counts[segment_id] += 1
        return current_coverage

    def average_coverage(self):
        return sum(self.segments) / len(self.segments)

    def average_nonzero_coverage(self):
        return sum(c for c in self.segments if c != 0) / sum(1 for c in self.segments if c != 0)

    def num_spans(self):
        return sum(self.segment_counts)

    def _coverage_stats(segments):
        """return (min,max,avg) coverage in segments"""
        if segments == []:
            return None, None, None
        min_coverage = segments[0]
        max_coverage = segments[0]
        avg_coverage = segments[0]
        for coverage in segments[1:]:
            min_coverage = min(coverage, min_coverage)
            max_coverage = max(coverage, max_coverage)
            avg_coverage += coverage
        avg_coverage /= len(segments)
        return min_coverage, max_coverage, avg_coverage

    def _density_stats(segment_counts):
        """return (min,max,avg) number of spans in segments"""
        if segment_counts == []:
            return None, None, None
        min_density = segment_counts[0]
        max_density = segment_counts[0]
        avg_density = segment_counts[0]
        for density in segment_counts[1:]:
            min_density = min(density, min_density)
            max_density = max(density, max_density)
            avg_density += density
        avg_density /= len(segment_counts)
        return min_density, max_density, avg_density

    def converage_stats(self):
        return Segments._coverage_stats(self.segments)

    def density_stats(self):
        return Segments._density_stats(self.segment_counts)


class ApproxTimeline(object):
    def __init__(self, begin_time, end_time):
        self.begin_time = begin_time
        self.end_time = end_time
        self.num_segments = 1_000_000
        self.segment_extent = (
            self.end_time - self.begin_time) // self.num_segments
        self.num_segments += 1
        self.gpu_kernel_tracks = {}
        self.comm_tracks = {}

    def empty_track(self):
        return Segments(self.num_segments)

    def get_segment_id(self, timestamp):
        span_id = int((timestamp - self.begin_time) // self.segment_extent)
        assert span_id >= 0
        assert span_id < self.num_segments
        return span_id

    def add_span(self, track, start, end):
        # get the track and the segment ids that the span starts and stops in
        start_id = self.get_segment_id(start)
        end_id = self.get_segment_id(end)

        for segment_id in range(start_id, end_id + 1):
            if segment_id == start_id and segment_id == end_id:
                coverage = (end - start) / self.segment_extent
                # logger.debug("[{}-{}] / {} = {} (contained)".format(start_ns, end_ns, span_size, coverage))
                assert(coverage >= 0.0)
                assert(coverage <= 1.0)
            elif segment_id == start_id:
                segment_start = start_id * self.segment_extent + self.begin_time
                coverage = 1.0 - (start - segment_start) / self.segment_extent
                # logger.debug("[{}-{}] / {} = {}".format(start_ns, span_start + span_size, span_size, coverage))
                assert(coverage >= 0.0)
                assert(coverage <= 1.0)
            elif segment_id == end_id:
                segment_start = end_id * self.segment_extent + self.begin_time
                coverage = (end - segment_start) / self.segment_extent
                # logger.debug("[{}-{}] / {} = {}".format(span_start, end_ns, span_size, coverage))
                assert(coverage >= 0.0)
                assert(coverage <= 1.0)
            else:
                coverage = 1.0

            track.add_coverage(segment_id, coverage)

    def add_gpu_span(self, gpu_id, start, end):
        if gpu_id not in self.gpu_kernel_tracks:
            self.gpu_kernel_tracks[gpu_id] = self.empty_track()
        self.add_span(self.gpu_kernel_tracks[gpu_id], start, end)

    def add_comm_span(self, src_tag, dst_tag, start, end):
        track_id = str(src_tag) + "-" + str(dst_tag)
        if track_id not in self.comm_tracks:
            self.comm_tracks[track_id] = self.empty_track()
        self.add_span(self.comm_tracks[track_id], start, end)


@click.command()
@click.argument('filename')
@click.pass_context
def summary(ctx, filename):

    logging.debug("Opening {}".format(filename))
    conn = sqlite3.connect(filename)
    c = conn.cursor()

    search_tables = [
        'CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL',
        'CUPTI_ACTIVITY_KIND_MEMCPY',
        'CUPTI_ACTIVITY_KIND_MEMCPY2',
        'CUPTI_ACTIVITY_KIND_KERNEL',
    ]

    begins = []
    ends = []
    for table_name in search_tables:
        if table_exists(c, table_name):
            logging.debug("Counting rows in {}".format(table_name))
            begin, end = table_time_extent(c, table_name)
            if begin and end:
                logger.debug("{}: has events from {} to {}".format(
                    table_name, begin, end))
                begins += [begin]
                ends += [end]

    begin = min(begins)
    end = max(ends)
    logger.debug("Paritioning time between {} and {} = {}".format(
        begin, end, end-begin))

    target_num_spans = 1_000_000
    span_size = (end-begin) // target_num_spans
    logger.debug(
        "targeting {} spans -> span size: {}".format(target_num_spans, span_size))
    AT = ApproxTimeline(begin, end)

    logger.debug("reading table CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL...")
    for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL"):
        start_ns = row[6]
        end_ns = row[7]
        gpu_id = row[9]
        AT.add_gpu_span(gpu_id, start_ns, end_ns)

    logger.debug("reading table CUPTI_ACTIVITY_KIND_KERNEL...")
    for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_KERNEL"):
        start_ns = row[6]
        end_ns = row[7]
        gpu_id = row[9]
        AT.add_gpu_span(gpu_id, start_ns, end_ns)

    logger.debug("reading table CUPTI_ACTIVITY_KIND_MEMCPY...")
    for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_MEMCPY"):
        src_kind = row[2]
        dst_kind = row[3]
        start_ns = row[6]
        end_ns = row[7]
        device_id = row[8]
        if src_kind == cupti.activity_memory_kind.DEVICE:
            src_tag = 'gpu' + str(device_id)
        else:
            src_tag = 'cpu'
        if dst_kind == cupti.activity_memory_kind.DEVICE:
            dst_tag = 'gpu' + str(device_id)
        else:
            dst_tag = 'cpu'
        AT.add_comm_span(src_tag, dst_tag, start_ns, end_ns)

    logger.debug("reading table CUPTI_ACTIVITY_KIND_MEMCPY2...")
    for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_MEMCPY2"):
        start_ns = row[6]
        end_ns = row[7]
        src_gpu = row[11]
        dst_gpu = row[13]
        src_tag = 'gpu' + str(src_gpu)
        dst_tag = 'gpu' + str(dst_gpu)
        AT.add_comm_span(src_tag, dst_tag, start_ns, end_ns)

    for gpu_id in AT.gpu_kernel_tracks:
        track = AT.gpu_kernel_tracks[gpu_id]
        pfx = "kernels::{}: ".format(gpu_id)
        print(pfx + " ({})".format(track.num_spans()))
        mi, ma, av = track.converage_stats()
        print(pfx + " avg coverage = {}".format(av))
        print(pfx + " min coverage = {}".format(mi))
        print(pfx + " max coverage = {}".format(ma))
        mi, ma, avg = track.density_stats()
        print(pfx + " avg density = {}".format(av))
        print(pfx + " min density = {}".format(mi))
        print(pfx + " max density = {}".format(ma))
    for comm_id in AT.comm_tracks:
        track = AT.comm_tracks[comm_id]
        pfx = "comm::{}: ".format(comm_id)
        print(pfx + " ({})".format(track.num_spans()))
        mi, ma, av = track.converage_stats()
        print(pfx + " avg coverage = {}".format(av))
        print(pfx + " min coverage = {}".format(mi))
        print(pfx + " max coverage = {}".format(ma))
        mi, ma, avg = track.density_stats()
        print(pfx + " avg density = {}".format(av))
        print(pfx + " min density = {}".format(mi))
        print(pfx + " max density = {}".format(ma))

    # create a new track with comm/kernel overlap

    # span_coverage = [1.0 - e for e in spans]
    # print("avg coverage:           ", sum(span_coverage)/len(span_coverage))
    # print("min coverage:           ", min(span_coverage))
    # print("max coverage:           ", max(span_coverage))
    # print("avg density:            ", sum(span_counts)/float(len(span_counts)))
    # print("min density:            ", min(span_counts))
    # print("max density:            ", max(span_counts))

    # nonzero_coverage = [span_coverage[i] for i in range(len(span_counts)) if span_counts[i] != 0]
    # nonzero_counts = [e for e in span_counts if e != 0]
    # print("avg coverage (nonzero): ", sum(nonzero_coverage)/len(nonzero_coverage))
    # print("min coverage (nonzero): ", min(nonzero_coverage))
    # print("max coverage (nonzero): ", max(nonzero_coverage))
    # print("avg density (nonzero):  ", sum(nonzero_counts)/float(len(nonzero_counts)))
    # print("min density (nonzero):  ", min(nonzero_counts))
    # print("max density (nonzero):  ", max(nonzero_counts))
