#include "openvprof/record.hpp"

using nlohmann::json;

namespace openvprof {


json NvmlCudaDriverVersionRecord::to_json() const{
    return json{{"version", version}};
}


} // namespace openvprof