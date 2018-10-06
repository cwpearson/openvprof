#include "openvprof/nvml_record.hpp"
#include "openvprof/json_fields.hpp"

using nlohmann::json;
using std::chrono::duration_cast;
using std::chrono::nanoseconds;

namespace openvprof {

json NvmlPstateRecord::to_json() const {
    return json {
        {DEVICE_ID, dev_},
        {PSTATE, pstate_},
        {WALL_START_NS, duration_cast<nanoseconds>(when_.time_since_epoch()).count()},
    };
}

json NvmlNvlinkUtilizationCounterRecord::to_json() const {
  
  return json{
      {KIND, "nvlink_utilization_counter"},
      {WALL_START_NS, ns_since_epoch(start_)},
      {BYTES, val_},
      {DEVICE_ID, dev_},
      {LINK_ID, link_},
      {COUNTER_ID, counter_id_},
  };
}

} // namespace openvprof