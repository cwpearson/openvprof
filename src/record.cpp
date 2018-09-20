#include "openvprof/record.hpp"

using nlohmann::json;

namespace openvprof {


json NvmlCudaDriverVersionRecord::to_json() const{
    return json{{"cuda_driver_version", version}};
}

json NvmlPstateRecord::to_json() const{
    return json{{"pstate", pstate_}};
}

} // namespace openvprof