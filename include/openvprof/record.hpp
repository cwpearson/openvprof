#pragma once

#include <chrono>

#include <nlohmann/json.hpp>

namespace openvprof {

class Record {
    public:
        virtual nlohmann::json to_json() const = 0;
        virtual ~Record() {}

};

class InstantRecord : public Record {
    public:
        InstantRecord(std::chrono::high_resolution_clock::time_point &when) : when_(when) {}

    protected:
        std::chrono::high_resolution_clock::time_point when_;

    public:
        virtual nlohmann::json to_json() const {
            return nlohmann::json{{"wall_time_point_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(when_.time_since_epoch()).count()}};
        }

};


class NvmlCudaDriverVersionRecord : public Record {
 public:
  int version;
  nlohmann::json to_json() const override;
};


class NvmlPstateRecord : public Record {
 public:
  int pstate_;
  nlohmann::json to_json() const override;
};


class SpanRecord : public Record {
    public:
    SpanRecord(uint64_t start_ns, uint64_t end_ns)
    : start_(std::chrono::nanoseconds(start_ns)),
      duration_(std::chrono::nanoseconds(end_ns - start_ns)) {

    }

    protected:
    std::chrono::high_resolution_clock::time_point start_;
    std::chrono::duration<double> duration_;

    public:
        virtual nlohmann::json to_json() const {
            return nlohmann::json{
                {"wall_start_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(start_.time_since_epoch()).count()},
                {"wall_duration_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(duration_).count()}
            };
        }
};


class SpanCorrelationRecord : public SpanRecord {
    public:
    SpanCorrelationRecord(uint64_t start_ns, uint64_t end_ns, uint32_t correlation_id)
    : SpanRecord(start_ns, end_ns), correlation_id_(correlation_id) {}


    protected:
    uint32_t correlation_id_;

    public:
        virtual nlohmann::json to_json() const {
            auto j = SpanRecord::to_json();
            j["correlation"] = correlation_id_;
            return j;
            return nlohmann::json{
                {"wall_start_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(start_.time_since_epoch()).count()},
                {"wall_duration_ns", std::chrono::duration_cast<std::chrono::nanoseconds>(duration_).count()}
            };
        }
};


class CuptiActivityKernelRecord : public SpanCorrelationRecord {
public:
    uint32_t correlation_id_;
    CuptiActivityKernelRecord(uint64_t start, uint64_t end, const uint32_t correlation_id) : SpanCorrelationRecord(start, end, correlation_id) {}
    nlohmann::json to_json() const override;
};


class CuptiActivityMemcpyRecord : public SpanCorrelationRecord {
public:
    std::string copy_kind_;
    std::string src_kind_;
    std::string dst_kind_;
    CuptiActivityMemcpyRecord(uint64_t start, uint64_t end, const uint32_t correlation_id,
    const char *copy_kind, const char *src_kind, const char *dst_kind) : SpanCorrelationRecord(start, end, correlation_id), copy_kind_(copy_kind), src_kind_(src_kind), dst_kind_(dst_kind) {}
    nlohmann::json to_json() const override;
};


// convert any record to json implicitly
void to_json(nlohmann::json &j, const Record &r);

}