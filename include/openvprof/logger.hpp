#pragma once

#include <memory>

#include <spdlog/spdlog.h>

namespace logger {
  extern std::shared_ptr<spdlog::logger> console;
}

#define LOG(level, ...) logger::console->level(__VA_ARGS__)

