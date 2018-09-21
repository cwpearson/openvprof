#pragma once

#include <boost/lockfree/queue.hpp>

#include "openvprof/record.hpp"

using boost::lockfree::queue;

namespace openvprof {
    void initTrace(queue<Record*> *recods);
    void finalizeTrace();
}

