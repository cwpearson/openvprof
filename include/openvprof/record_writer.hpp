#pragma once

#include <thread>
#include <string>

#include <boost/lockfree/queue.hpp>

#include "openvprof/record.hpp"
#include "openvprof/logger.hpp"

namespace openvprof{

class RecordWriter {
public:
    enum class Signal {
        CONTINUE,
        STOP
    };

  RecordWriter() : records_(nullptr), signal_(Signal::STOP) {}

  RecordWriter(boost::lockfree::queue<Record*> *records, const std::string &output_path) 
  : records_(records), output_path_(output_path), signal_(Signal::STOP) {}

  // create and start the polling thread
  void start() {
      signal_ = Signal::CONTINUE;
      LOG(trace, "starting RecordWriter thread");
      thread_ = std::thread(&RecordWriter::run, this);
  }

  // finish the polling thread
  void stop() {
      signal_ = Signal::STOP;
      LOG(trace, "waiting for join");
      thread_.join();
  }

  void pause() {
      LOG(warn, "ignoring pause");
  }

  void resume() {
      LOG(warn, "ignoring resume");
  }



private:
  boost::lockfree::queue<Record*> *records_;
  std::string output_path_;
  volatile Signal signal_;
  std::thread thread_;


  // the code executed by the polling thread
  void run();

};


} // namespace openvprof