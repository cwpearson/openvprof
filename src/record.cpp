#include "openvprof/record.hpp"

using nlohmann::json;

namespace openvprof {


json NvmlCudaDriverVersionRecord::to_json() const {
    return json{{"cuda_driver_version", version}};
}


json NvmlPstateRecord::to_json() const{
    return json{{"pstate", pstate_}};
}


json CuptiActivityKernelRecord::to_json() const{
    auto j = SpanCorrelationRecord::to_json();
    j["kind"] = "activity_kernel";
    return j;
}

json CuptiActivityMemcpyRecord::to_json() const{
    auto j = SpanCorrelationRecord::to_json();
    j["kind"] = "activity_memcpy";
    j["copy_kind"] = copy_kind_;
    j["src_kind"] = src_kind_;
    j["dst_kind"] = dst_kind_;
    return j;
}

void to_json(nlohmann::json &j, const Record &r) {
    j = r.to_json();
}

} // namespace openvprof