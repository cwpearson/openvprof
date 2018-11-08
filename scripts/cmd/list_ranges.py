import click
import logging
from nvprof.db import Db
from datetime import datetime

logger = logging.getLogger(__name__)


@click.command()
@click.argument('filename')
@click.option('--group', is_flag=True)
@click.pass_context
def list_ranges(ctx, filename, group):
    db = Db(filename)

    logger.debug("Loading strings")
    nvprof_id_to_string, nvprof_string_to_id = db.get_strings()

    logger.debug("Loading ranges")
    groups = {}
    for row in db.execute("select id, Max(name), Min(timestamp), Max(timestamp) from CUPTI_ACTIVITY_KIND_MARKER group by id"):
        name_idx = row[1]
        name = nvprof_id_to_string[name_idx]
        start = row[2]
        end = row[3]
        if group:
            if name not in groups:
                groups[name] = []
            groups[name] += [(start, end)]
        else:
            print(name, start, end)

    if group:
        print("name\tcount\tmin\tmax\tavg")
        for key in groups:
            g = groups[key]
            mi = g[0][1] - g[0][0]
            ma = g[0][1] - g[0][0]
            avg = g[0][1] - g[0][0]
            for e in g[1:]:
                mi = min(e[1] - e[0], mi)
                ma = max(e[1] - e[0], ma)
                avg += e[1] - e[0]
            avg /= len(g)
            print(key, len(g), mi, ma, avg)
