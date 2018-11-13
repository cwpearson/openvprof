import click
import logging
from nvprof.db import Db
from datetime import datetime
import math

logger = logging.getLogger(__name__)


@click.command()
@click.argument('filename')
@click.option('--group/--no-group', default=True, help="group ranges by name")
@click.option('--sort', type=click.Choice(['count', 'min', 'max', 'avg', 'tot']), default="tot")
@click.pass_context
def list_ranges(ctx, filename, group, sort):
    """print summary statistics of ranges"""

    db = Db(filename)

    logger.debug("Loading strings")
    strings, _ = db.get_strings()

    logger.debug("Loading ranges")
    groups = {}
    for record in db.records(['CUPTI_ACTIVITY_KIND_RANGE']):

        name = record.name
        start = record.start
        end = record.end
        if group:
            if name not in groups:
                groups[name] = []
            groups[name] += [(start, end)]
        else:
            print(name, start, end)

    ordered_output = []
    if group:
        print("count\ttot(s)\tmin(s)\tmax(s)\tavg(s)\tstddev(s)\tname")
        for key in groups:
            g = groups[key]
            mi = g[0][1] - g[0][0]
            ma = g[0][1] - g[0][0]
            tot = g[0][1] - g[0][0]
            for e in g[1:]:
                mi = min(e[1] - e[0], mi)
                ma = max(e[1] - e[0], ma)
                tot += e[1] - e[0]
            avg = tot / len(g)
            va = (g[0][1] - g[0][0] - avg) ** 2
            for e in g[1:]:
                va += (e[1] - e[0] - avg) ** 2
            if len(g) == 1:
                va = 0
            else:
                va /= (len(g) - 1)
            stddev = math.sqrt(va)
            ordered_output += [(len(g), tot/1e9, mi/1e9,
                                ma/1e9, avg/1e9, stddev/1e9, key)]

        sort_by = {
            'count': 0,
            'tot': 1,
            'min': 2,
            'max': 3,
            'avg': 4,
            'stddev': 5,
        }

        ordered_output = sorted(
            ordered_output, reverse=True, key=lambda t: t[sort_by[sort]])

        for t in ordered_output:
            print(*t)
