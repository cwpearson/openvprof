#include "openvprof/record.hpp"
#include "openvprof/cupti_utils.hpp"

using nlohmann::json;
using std::chrono::high_resolution_clock;

static const char *CBID = "cbid";
static const char *CONTEXT_ID = "ctx";
static const char *COPY_KIND = "copy_kind";
static const char *CORRELATION_ID = "cor";
static const char *DEVICE_ID = "dev";
static const char *DST_ID = "dst_id";
static const char *DST_KIND = "dst_kind";
static const char *KIND = "kind";
static const char *NAME = "name";
static const char *PROCESS_ID = "pid";
static const char *SRC_ID = "src_id";
static const char *SRC_KIND = "src_kind";
static const char *STREAM_ID = "stream";
static const char *THREAD_ID = "tid";
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
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_GPU_PAGE_FAULT:
        return "GPU_PAGE_FAULT";
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_CPU_PAGE_FAULT_COUNT:
        return "CPU_PAGE_FAULT";
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_THRASHING:
        return "THRASH";
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_THROTTLING:
        return "THROTTLE";
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_REMOTE_MAP:
        return "MAP";
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_BYTES_TRANSFER_DTOD:
        return "BYTES_TRANSFER_DTOD";
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
    auto j = InstantRecord::to_json();
    j["pstate"] = pstate_;
    return j;
}


json CuptiActivityApiRecord::to_json() const{
    return json {
        {KIND, "activity_api"},
        {WALL_START_NS, api_.start},
        {WALL_DURATION_NS, api_.end - api_.start},
        {PROCESS_ID, api_.processId},
        {THREAD_ID, api_.threadId},
        {CORRELATION_ID, api_.correlationId},
        {CBID, getDriverCbidName(static_cast<CUpti_driver_api_trace_cbid>(api_.cbid))},
    };
}

json CuptiActivityKernelRecord::to_json() const{
    return json {
        {KIND, "activity_kernel"},
        {WALL_START_NS, kernel_.start},
        {WALL_DURATION_NS, kernel_.end - kernel_.start},
        {NAME, kernel_.name},
        {DEVICE_ID, kernel_.deviceId}, 
        {CONTEXT_ID, kernel_.contextId}, 
        {STREAM_ID, kernel_.streamId},
    };
}

json CuptiActivityMemcpyRecord::to_json() const{
    auto j = SpanCorrelationRecord::to_json();
    j[KIND] = "activity_memcpy";
    j[COPY_KIND] = copy_kind_;
    j[SRC_KIND] = src_kind_;
    j[DST_KIND] = dst_kind_;
    return j;
}

json CuptiActivityUnifiedMemoryCounterRecord::to_json() const {
    return json{
        {WALL_START_NS, raw_.start},
        {WALL_DURATION_NS, raw_.end - raw_.start},
        {UVM_COUNTER_KIND, getUvmCounterKindString(raw_.counterKind)},
        {VALUE, raw_.value},
        {SRC_ID, raw_.srcId},
        {DST_ID, raw_.dstId},
    };
}

void to_json(nlohmann::json &j, const Record &r) {
    j = r.to_json();
}

} // namespace openvprof