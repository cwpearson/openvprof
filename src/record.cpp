#include "openvprof/record.hpp"
#include "openvprof/cupti_utils.hpp"
#include "openvprof/logger.hpp"
#include "openvprof/json_fields.hpp"

using nlohmann::json;
using std::chrono::high_resolution_clock;



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


json CuptiActivityApiRecord::to_json() const{

    auto j = json {
        {WALL_START_NS, api_.start},
        {WALL_DURATION_NS, api_.end - api_.start},
        {PROCESS_ID, api_.processId},
        {THREAD_ID, api_.threadId},
        {CORRELATION_ID, api_.correlationId},
    };

    if (CUPTI_ACTIVITY_KIND_DRIVER == api_.kind) {
        j[KIND] = "activity_api_driver";
        j[CBID] = getDriverCbidName(static_cast<CUpti_driver_api_trace_cbid>(api_.cbid));
    } else if (CUPTI_ACTIVITY_KIND_RUNTIME == api_.kind) {
        j[KIND]= "activity_api_runtime";
        j[CBID]= getRuntimeCbidName(static_cast<CUpti_runtime_api_trace_cbid>(api_.cbid));
    } else {
        LOG(warn, "Unexpected cupti activity api record");
        j[KIND] = "activity_api_unknown";
    }

    return j;
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
      // printf("MEMCPY %s [ %llu - %llu ] device %u, context %u, stream %u, correlation %u/r%u\n",
      //        getMemcpyKindString((CUpti_ActivityMemcpyKind) memcpy->copyKind),
      //        (unsigned long long) (memcpy->start - startTimestamp),
      //        (unsigned long long) (memcpy->end - startTimestamp),
      //        memcpy->deviceId, memcpy->contextId, memcpy->streamId,
      //        memcpy->correlationId, memcpy->runtimeCorrelationId);




    return json {
        {KIND, "activity_memcpy"},
        {WALL_START_NS, memcpy_.start},
        {WALL_DURATION_NS, memcpy_.end - memcpy_.start},
        {BYTES, memcpy_.bytes},
        {COPY_KIND, getMemcpyKindString(static_cast<CUpti_ActivityMemcpyKind>(memcpy_.copyKind))},
        {SRC_KIND,  getMemoryKindString(static_cast<CUpti_ActivityMemoryKind>(memcpy_.srcKind))},
        {DST_KIND,  getMemoryKindString(static_cast<CUpti_ActivityMemoryKind>(memcpy_.dstKind))},
        {DEVICE_ID, memcpy_.deviceId},
    };
}

json CuptiActivityUnifiedMemoryCounterRecord::to_json() const {
    // raw_.pad;

    auto j = json{
        {KIND, "activity_unified_memory_counter"},
        {WALL_START_NS, raw_.start},
        {WALL_DURATION_NS, raw_.end - raw_.start},
        {UVM_COUNTER_KIND, getUvmCounterKindString(raw_.counterKind)},
        {VALUE, raw_.value},
        {SRC_ID, raw_.srcId},
        {DST_ID, raw_.dstId},
        {ADDRESS, raw_.address},
    };


    switch (raw_.counterKind) {
        case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_GPU_PAGE_FAULT: {
            auto ty = static_cast<CUpti_ActivityUnifiedMemoryAccessType>(raw_.flags);
        }
        case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_BYTES_TRANSFER_HTOD:
        case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_BYTES_TRANSFER_DTOH: {
            auto cause = static_cast<CUpti_ActivityUnifiedMemoryMigrationCause>(raw_.flags);
        }
        case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_REMOTE_MAP: {
            auto cause = static_cast<CUpti_ActivityUnifiedMemoryRemoteMapCause>(raw_.flags);
        }
        case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_THRASHING:
        case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_THROTTLING: {
            auto flag = static_cast<CUpti_ActivityFlag>(raw_.flags);
        }
    }


    return j;
}

void to_json(nlohmann::json &j, const Record &r) {
    j = r.to_json();
}

} // namespace openvprof