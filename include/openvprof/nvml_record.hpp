#pragma once

#include <nvml.h>

#include "openvprof/record.hpp"


namespace openvprof {

class NvmlPstateRecord : public Record {
 public:
  NvmlPstateRecord(unsigned int dev, time_point &when, nvmlPstates_t pstate) : dev_(dev), pstate_(pstate), when_(when) {}
  unsigned int dev_;
  nvmlPstates_t pstate_;
  time_point when_;
  nlohmann::json to_json() const override;
};

} // namespace openvprof