#pragma once

#include <chrono>

namespace openvprof {
    typedef std::chrono::high_resolution_clock::time_point time_point;
    time_point now();
    size_t ns_since_epoch(const time_point &t);
}