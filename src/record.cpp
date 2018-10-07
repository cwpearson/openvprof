#include <sstream>
#include <iomanip>

#include "openvprof/record.hpp"
#include "openvprof/cupti_utils.hpp"
#include "openvprof/logger.hpp"
#include "openvprof/json_fields.hpp"

using nlohmann::json;
using std::chrono::high_resolution_clock;

std::string hexStr(const char *data, int len)
{
    std::stringstream ss;
    ss << std::hex << std::setfill('0');
    for (int i(0); i < len; ++i)
        ss << std::setw(2) << static_cast<int>(data[i]);
    return ss.str();
}

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

namespace openvprof
{

json NvmlCudaDriverVersionRecord::to_json() const
{
    return json{{"cuda_driver_version", version}};
}

json CuptiActivityApiRecord::to_json() const
{

    auto j = json{
        {WALL_START_NS, api_.start},
        {WALL_DURATION_NS, api_.end - api_.start},
        {PROCESS_ID, api_.processId},
        {THREAD_ID, api_.threadId},
        {CORRELATION_ID, api_.correlationId},
    };

    if (CUPTI_ACTIVITY_KIND_DRIVER == api_.kind)
    {
        j[KIND] = "activity_api_driver";
        j[CBID] = getDriverCbidName(static_cast<CUpti_driver_api_trace_cbid>(api_.cbid));
    }
    else if (CUPTI_ACTIVITY_KIND_RUNTIME == api_.kind)
    {
        j[KIND] = "activity_api_runtime";
        j[CBID] = getRuntimeCbidName(static_cast<CUpti_runtime_api_trace_cbid>(api_.cbid));
    }
    else
    {
        LOG(warn, "Unexpected cupti activity api record");
        j[KIND] = "activity_api_unknown";
    }

    return j;
}

json CuptiActivityKernelRecord::to_json() const
{
    return json{
        {KIND, "activity_kernel"},
        {WALL_START_NS, kernel_.start},
        {WALL_DURATION_NS, kernel_.end - kernel_.start},
        {NAME, kernel_.name},
        {DEVICE_ID, kernel_.deviceId},
        {CONTEXT_ID, kernel_.contextId},
        {STREAM_ID, kernel_.streamId},
    };
}

json CuptiActivityMemcpyRecord::to_json() const
{
    // printf("MEMCPY %s [ %llu - %llu ] device %u, context %u, stream %u, correlation %u/r%u\n",
    //        getMemcpyKindString((CUpti_ActivityMemcpyKind) memcpy->copyKind),
    //        (unsigned long long) (memcpy->start - startTimestamp),
    //        (unsigned long long) (memcpy->end - startTimestamp),
    //        memcpy->deviceId, memcpy->contextId, memcpy->streamId,
    //        memcpy->correlationId, memcpy->runtimeCorrelationId);

    return json{
        {KIND, "activity_memcpy"},
        {WALL_START_NS, memcpy_.start},
        {WALL_DURATION_NS, memcpy_.end - memcpy_.start},
        {BYTES, memcpy_.bytes},
        {COPY_KIND, getMemcpyKindString(static_cast<CUpti_ActivityMemcpyKind>(memcpy_.copyKind))},
        {SRC_KIND, getMemoryKindString(static_cast<CUpti_ActivityMemoryKind>(memcpy_.srcKind))},
        {DST_KIND, getMemoryKindString(static_cast<CUpti_ActivityMemoryKind>(memcpy_.dstKind))},
        {DEVICE_ID, memcpy_.deviceId},
    };
}

json CuptiActivityUnifiedMemoryCounterRecord::to_json() const
{
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

    switch (raw_.counterKind)
    {
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_GPU_PAGE_FAULT:
    {
        auto ty = static_cast<CUpti_ActivityUnifiedMemoryAccessType>(raw_.flags);
        break;
    }
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_BYTES_TRANSFER_HTOD:
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_BYTES_TRANSFER_DTOH:
    {
        auto cause = static_cast<CUpti_ActivityUnifiedMemoryMigrationCause>(raw_.flags);
        break;
    }
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_REMOTE_MAP:
    {
        auto cause = static_cast<CUpti_ActivityUnifiedMemoryRemoteMapCause>(raw_.flags);
        break;
    }
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_THRASHING:
    case CUPTI_ACTIVITY_UNIFIED_MEMORY_COUNTER_KIND_THROTTLING:
    {
        auto flag = static_cast<CUpti_ActivityFlag>(raw_.flags);
        break;
    }
    }

    return j;
}

/*
 NVIDIA NVLink is a high-bandwidth, energy-efficient interconnect that enables fast communication between the CPU and GPU, and between GPUs. CUPTI provides NVLink topology information and NVLink transmit/receive throughput metrics.

Activity record CUpti_ActivityNVLink2 enabled using activity kind CUPTI_ACTIVITY_KIND_NVLink outputs NVLink topology information in terms of logical NVLinks. A logical NVLink is connected between 2 devices, the device can be of type NPU (NVLink Processing Unit which can be CPU) or GPU. Each device can support upto 6 NVLinks hence one logical link can comprise of 1 to 6 physical NVLinks. Field physicalNvLinkCount gives number of physical links in this logical link. Fields portDev0 and portDev1 give information about the slot in which physical NVLinks are connected for a logical link. This port is same as instance of NVLink metrics profiled from a device. So port and instance information should be used to correlate the per-instance metric values with the physical NVLinks and in turn to the topology. Field flag gives the properties of a logical link, whether the link has access to system memory or peer device memory, and have capabilities to do system memory or peer memmory atomics. Field bandwidth gives the bandwidth of the logical link in kilobytes/sec.

CUPTI also provides some metrics for each physical links. Metrics are provided for data transmitted/received, transmit/receive throughput and header versus user data overhead for each physical NVLink. These metrics are also provided per packet type (read/write/ atomics/response) to get more detailed insight in the NVLink traffic. 
*/

/*
  union {
    CUuuid    uuidDev;
    struct {
      //Index of the NPU. First index will always be zero.
       
      uint32_t  index;
      //Domain ID of NPU. On Linux, this can be queried using lspci.
       
      uint32_t  domainId;
    } npu;
  } idDev1;

*/

json CuptiActivityNvlinkRecord::to_json() const
{

    json j = {
        {KIND, "activity_nvlink"},
    };

    if (nvlink_.typeDev0 == CUPTI_DEV_TYPE_GPU)
    {
        j["uuid0"] = hexStr(nvlink_.idDev0.uuidDev.bytes, 16);
        j["type0"] = "gpu";
    }
    else if (nvlink_.typeDev0 == CUPTI_DEV_TYPE_NPU)
    {
        j["type0"] = "npu";
        j["id0"] = nvlink_.idDev0.npu.index;
        j["domain_id0"] = nvlink_.idDev0.npu.domainId;
    }
    else
    {
        LOG(error, "unexpected CuptiActivityNVLink2::typeDev0");
        j["type0"] = "unknown";
    }

    if (nvlink_.typeDev1 == CUPTI_DEV_TYPE_GPU)
    {
        j["uuid1"] = hexStr(nvlink_.idDev1.uuidDev.bytes, 16);
        j["type1"] = "gpu";
    }
    else if (nvlink_.typeDev1 == CUPTI_DEV_TYPE_NPU)
    {
        j["type1"] = "npu";
        j["id1"] = nvlink_.idDev1.npu.index;
        j["domain_id1"] = nvlink_.idDev1.npu.domainId;
    }
    else
    {
        LOG(error, "unexpected CuptiActivityNVLink2::typeDev1");
        j["type1"] = "unknown";
    }

    return j;
}

void to_json(nlohmann::json &j, const Record &r)
{
    j = r.to_json();
}

} // namespace openvprof