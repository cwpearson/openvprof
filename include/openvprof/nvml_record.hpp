#pragma once

#include <nvml.h>

#include "openvprof/record.hpp"
#include "openvprof/time.hpp"


namespace openvprof {

class NvmlPstateRecord : public Record {
 public:
  NvmlPstateRecord(unsigned int dev, time_point &when, nvmlPstates_t pstate) : dev_(dev), pstate_(pstate), when_(when) {}
  unsigned int dev_;
  nvmlPstates_t pstate_;
  time_point when_;
  nlohmann::json to_json() const override;
};

class NvmlNvlinkUtilizationCounterRecord : public Record {
 public:
  NvmlNvlinkUtilizationCounterRecord(
    time_point &start,
      unsigned int devId, 
      unsigned int linkId, 
      unsigned long long val,
      unsigned int counterId,
      bool tx) : start_(start), dev_(devId), link_(linkId), val_(val), counter_id_(counterId), tx_(tx) {}
  
  time_point start_;
  unsigned int dev_;
  unsigned int link_;
  unsigned long long val_;
  unsigned int counter_id_;
  bool tx_;
  nlohmann::json to_json() const override;
};

} // namespace openvprof