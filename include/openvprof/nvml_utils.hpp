#pragma once

#include "openvprof/time.hpp"

namespace openvprof {

typedef struct {
    unsigned long long val;
    time_point timestamp;
} TimestampValue;

} // namespace openvprof