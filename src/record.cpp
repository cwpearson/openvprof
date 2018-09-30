#include "openvprof/record.hpp"

using nlohmann::json;


static const char *CORRELATION = "cor";
static const char *DST = "dst";
static const char *KIND = "kind";
static const char *PROCESS = "pid";
static const char *SRC = "src";
static const char *THREAD = "tid";
static const char *UVM_COUNTER_KIND = "counter_kind";
static const char *VALUE = "value";
static const char *WALL_START_NS = "wall_start_ns";
static const char *WALL_DURATION_NS = "wall_duration_ns";

static const char *
getUvmCounterKindString(CUpti_ActivityUnifiedMemoryCounterKind kind)
{
    switch (kind) 
    {
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_BYTES_TRANSFER_HTOD:
        return "BYTES_TRANSFER_HTOD";
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_BYTES_TRANSFER_DTOH:
        return "BYTES_TRANSFER_DTOH";
    default:
        break;
    }
    return "<unknown>";
}

namespace openvprof {



json NvmlCudaDriverVersionRecord::to_json() const {
    return json{{"cuda_driver_version", version}};
}


json NvmlPstateRecord::to_json() const{
    return json{{"pstate", pstate_}};
}


json CuptiActivityKernelRecord::to_json() const{
    auto j = SpanCorrelationRecord::to_json();
    j[KIND] = "activity_kernel";
    return j;
}

json CuptiActivityMemcpyRecord::to_json() const{
    auto j = SpanCorrelationRecord::to_json();
    j[KIND] = "activity_memcpy";
    j["copy_kind"] = copy_kind_;
    j["src_kind"] = src_kind_;
    j["dst_kind"] = dst_kind_;
    return j;
}

json CuptiActivityUnifiedMemoryCounterRecord::to_json() const {
    return json{
        {WALL_START_NS, raw_.start},
        {WALL_DURATION_NS, raw_.end - raw_.start},
        {UVM_COUNTER_KIND, getUvmCounterKindString(raw_.counterKind)},
        {VALUE, raw_.value},
        {SRC, raw_.srcId},
        {DST, raw_.dstId},
    };
}

void to_json(nlohmann::json &j, const Record &r) {
    j = r.to_json();
}

} // namespace openvprof