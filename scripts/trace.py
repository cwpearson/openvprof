#! python3

def make_complete_event(r, start_time=0):

    kind = r.get("kind", None)

    if not kind:
        return None

    if kind == "activity_api_driver":
        start = (r["wall_start_ns"] - start_time)/1000
        dur = r["wall_duration_ns"]/1000
        pid = "pid"
        tid = "activity: driver"
        cat = "cat"
        name = r["cbid"]
        args = {}
    elif kind == "activity_api_runtime":
        start = (r["wall_start_ns"] - start_time)/1000
        dur = r["wall_duration_ns"]/1000
        pid = "pid"
        tid = "activity: runtime"
        cat = "cat"
        name = r["cbid"]
        args = {}
    elif kind == "activity_memcpy":
        start = (r["wall_start_ns"] - start_time)/1000
        dur = r["wall_duration_ns"]/1000
        pid = "pid"
        tid = "activity: memcpy"
        cat = "cat"
        name = r["copy_kind"]
        args = {
            "bytes": r["bytes"],
            "MB/s": (r["bytes"] / 1e6)      / (r["wall_duration_ns"] / 1e9),
            "MiB/s": (r["bytes"] / 2 ** 20) / (r["wall_duration_ns"] / 1e9),
        }
    elif kind == "activity_kernel":
        start = (r["wall_start_ns"] - start_time)/1000
        dur = r["wall_duration_ns"]/1000
        pid = "pid"
        tid = "activity: kernel"
        cat = "cat"
        name = r["name"]
        args = {}
    elif kind == "activity_unified_memory_counter":
        counter_kind = r["counter_kind"]
        if counter_kind == "CPU_PAGE_FAULT" or counter_kind == "THRASHING" or counter_kind == "MAP":
            return None
        start = (r["wall_start_ns"] - start_time)/1000
        dur = r["wall_duration_ns"]/1000
        pid = "pid"
        tid = "activity: um " + r["counter_kind"]
        cat = "cat"
        name = r["counter_kind"]
        args = {
            "value": r["value"]
        }
    else:
        return None

    return {
        "name": name,
        "cat": cat,
        "ph": "X",
        "pid": pid,
        "tid": tid,
        "ts": start,
        "dur": dur,
        "args": args
    }

import json

with open('openvprof.json') as f:
    j = json.load(f)

# find the starting timestamp, so we can normalize to that

start_time = None

for record in j:
    if "wall_start_ns" in record:
        if not start_time:
            start_time = record["wall_start_ns"]
        start_time = min(start_time, record["wall_start_ns"])

print("start time: {}".format(start_time))

trace = {
    "traceEvents": [],
    "displayTimeUnit": "ns",
}

for record in j:
    e = make_complete_event(record, start_time=start_time)
    if e:
        trace["traceEvents"] += [e]
    else:
        print("couldn't make event for", record)



with open("trace.json", "w") as f:
    json.dump(trace, f, indent=4)