import click
import sqlite3
import logging
import sys


logger = logging.getLogger(__name__)

# SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';

def table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='{0}'".format(table_name))
    row = cursor.fetchone()
    if row:
        return True
    return False

def min_max_element(cursor, table_name, column_name):
    cursor.execute('SELECT Min({0}), Max({0}) from {1}'.format(column_name, table_name))
    row = cursor.fetchone()
    return row[0], row[1]

def table_time_extent(cursor, table_name):
    cursor.execute('SELECT Min({0}), Max({0}), Min({1}), Max({1}) from {2}'.format('start', 'end', table_name))
    row = cursor.fetchone()
    begin = min(row[0], row[2]) if row[0] and row[2] else None
    end = min(row[1], row[3]) if row[1] and row[3] else None
    return begin, end


@click.command()
@click.argument('filename')
@click.pass_context
def summary(ctx, filename):
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
            begin, end = table_time_extent(c, table_name)
            if begin and end:
                logger.debug("{}: has events from {} to {}".format(table_name, begin, end))
                begins += [begin]
                ends += [end]

    begin = min(begins)
    end = max(ends)
    logger.debug("Paritioning time between {} and {} = {}".format(begin, end, end-begin))

    target_num_spans = 1_000_000
    span_size = (end-begin) // target_num_spans
    logger.debug("targeting {} spans -> span size: {}".format(target_num_spans, span_size))
    spans_begin = begin
    spans = [1.0 for i in range(target_num_spans + 1)] # fixme what if spans are evenly divisible
    span_counts = [0 for i in range(target_num_spans + 1)]

    # put in coverage from concurrent kernels
    for row in c.execute("SELECT * FROM CUPTI_ACTIVITY_KIND_CONCURRENT_KERNEL"):
        start_ns = row[6]
        end_ns = row[7]
        # logger.debug("event [{}-{}]".format(start_ns, end_ns))
        start_span_id = (start_ns - spans_begin) // span_size
        end_span_id = (end_ns - spans_begin) // span_size
        for span_id in range(start_span_id, end_span_id + 1):
            span_counts[span_id] += 1
            if span_id == start_span_id and span_id == end_span_id:
                coverage = (end_ns - start_ns) / span_size
                # logger.debug("[{}-{}] / {} = {} (contained)".format(start_ns, end_ns, span_size, coverage))
                assert(coverage >= 0.0)
                assert(coverage <= 1.0)
            elif span_id == start_span_id:
                span_start = start_span_id * span_size + spans_begin
                coverage = 1.0 - (start_ns - span_start) / span_size
                # logger.debug("[{}-{}] / {} = {}".format(start_ns, span_start + span_size, span_size, coverage))
                assert(coverage >= 0.0)
                assert(coverage <= 1.0)
            elif span_id == end_span_id:
                span_start = end_span_id * span_size + spans_begin
                coverage = (end_ns - span_start) / span_size
                # logger.debug("[{}-{}] / {} = {}".format(span_start, end_ns, span_size, coverage))
                assert(coverage >= 0.0)
                assert(coverage <= 1.0)
            else:
                coverage = 1.0

            uncovered = 1.0 - coverage
            spans[span_id] *= uncovered
            # logger.debug("span {} has additional coverage {} -> {} still free".format(span_id, coverage, spans[span_id]))
    
    span_coverage = [1.0 - e for e in spans]
    print("avg coverage:           ", sum(span_coverage)/len(span_coverage))
    print("min coverage:           ", min(span_coverage))
    print("max coverage:           ", max(span_coverage))
    print("avg density:            ", sum(span_counts)/float(len(span_counts)))
    print("min density:            ", min(span_counts))
    print("max density:            ", max(span_counts))

    nonzero_coverage = [span_coverage[i] for i in range(len(span_counts)) if span_counts[i] != 0]
    nonzero_counts = [e for e in span_counts if e != 0]
    print("avg coverage (nonzero): ", sum(nonzero_coverage)/len(nonzero_coverage))
    print("min coverage (nonzero): ", min(nonzero_coverage))
    print("max coverage (nonzero): ", max(nonzero_coverage))
    print("avg density (nonzero):  ", sum(nonzero_counts)/float(len(nonzero_counts)))
    print("min density (nonzero):  ", min(nonzero_counts))
    print("max density (nonzero):  ", max(nonzero_counts))

