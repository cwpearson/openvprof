#! python3


class Bandwidth(object):
    def __init__(self, start_time):
        self.start_time = start_time
        self.cpu_cpu_tracks = {}
        self.cpu_gpu_tracks = {}
        self.gpu_gpu_tracks = {}

    def handle(self, record):

        kind = record.get("kind", None)
        if kind == "activity_memcpy":
            bandwidth = record["bytes"] / (record["wall_duration_ns"] / 1e9)

            copy_kind = record["copy_kind"]
            if copy_kind == "HtoD":
                name = "cpu-gpu" + str(record["dev"])
            elif copy_kind == "DtoH":
                name = "gpu" + str(record["dev"]) + "-cpu"
            else:
                name = "generic"

            es = []
            es += [{
                "pid": 'bw',
                "name": name,
                "ph": "C",
                "ts": (record["wall_start_ns"] - self.start_time) / 1000,
                "args": {
                    "bw": bandwidth,
                },
            }]
            es += [{
                "pid": 'bw',
                "name": name,
                "ph": "C",
                "ts": ((record["wall_start_ns"] + record["wall_duration_ns"]) - self.start_time) / 1000,
                "args": {
                    "bw": 0,
                },
            }]

            return es
        elif kind == "activity_unified_memory_counter":
            counter_kind = record["counter_kind"]
            bandwidth = record["value"] / (record["wall_duration_ns"] / 1e9)
            if counter_kind == "BYTES_TRANSFER_DTOH":
                name = "gpu" + str(record["src_id"]) + "-cpu"
            elif counter_kind == "BYTES_TRANSFER_HTOD":
                name = "cpu-gpu" + str(record["dst_id"])
            else:
                return None

            es = []
            es += [{
                "pid": 'bw',
                "name": name,
                "ph": "C",
                "ts": (record["wall_start_ns"] - self.start_time) / 1000,
                "args": {
                    "bw": bandwidth,
                },
            }]
            es += [{
                "pid": 'bw',
                "name": name,
                "ph": "C",
                "ts": ((record["wall_start_ns"] + record["wall_duration_ns"]) - self.start_time) / 1000,
                "args": {
                    "bw": 0,
                },
            }]
            return es

        return None


class PcieBandwidth(object):
    def __init__(self, start_time):
        self.start_time = start_time

    def handle(self, record):

        kind = record.get("kind", None)
        if kind == "pcie_throughput":
            bandwidth = (record["kbytes"] * 1e3) / (record["wall_duration_ns"] / 1e9)

            name = "gpu" + str(record["dev"]) + "-" + record["cntr_kind"]

            es = []
            es += [{
                "pid": 'pcie_bw',
                "name": name,
                "ph": "C",
                "ts": (record["wall_start_ns"] - self.start_time) / 1000,
                "args": {
                    "bw": bandwidth,
                },
            }]
            es += [{
                "pid": 'pcie_bw',
                "name": name,
                "ph": "C",
                "ts": ((record["wall_start_ns"] + record["wall_duration_ns"]) - self.start_time) / 1000,
                "args": {
                    "bw": 0,
                },
            }]

            return es
        else:  # not a pcie throughput record
            return None


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
            "MB/s": (r["bytes"] / 1e6) / (r["wall_duration_ns"] / 1e9),
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
        "args": args,
        # "tdur": dur,
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

b = Bandwidth(start_time)
pcie_bw = PcieBandwidth(start_time)

for record in j:
    used = False
    e = make_complete_event(record, start_time=start_time)
    if e:
        trace["traceEvents"] += [e]
        used = True
    es = b.handle(record)
    if es:
        trace["traceEvents"] += es
        used = True
    es = pcie_bw.handle(record)
    if es:
        trace["traceEvents"] += es
        used = True
    if not used:
        print("didn't use record:", record)


with open("trace.json", "w") as f:
    json.dump(trace, f, indent=4)
