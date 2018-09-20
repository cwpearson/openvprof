#pragma once

#include <nlohmann/json.hpp>

namespace openvprof{

class Record {
    public:
        virtual nlohmann::json to_json() const = 0;

};

class NvmlCudaDriverVersionRecord : public Record {
 public:
  int version;
  nlohmann::json to_json() const override;
};

// convert any record to json implicitly
static void to_json(nlohmann::json &j, const Record &r) {
    j = r.to_json();
}

}