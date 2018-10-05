
cmake_minimum_required(VERSION 3.12 FATAL_ERROR)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_COLOR_MAKEFILE ON)
set_property(GLOBAL PROPERTY USE_FOLDERS ON)


  include("cmake/modules/HunterGate.cmake")
  HunterGate(
      URL "https://github.com/ruslo/hunter/archive/v0.23.1.tar.gz"
      SHA1 "51d2d6be411251c8de18c4ca20ef778880cf4cce"
      LOCAL 
  )

project(openvprof LANGUAGES C CXX CUDA VERSION 0.3.0)

set(CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake/modules ${CMAKE_MODULE_PATH})

include(CMakePackageConfigHelpers)
include(CTest)
include(GitGetRevisionDescription)


# set(CMAKE_POSITION_INDEPENDENT_CODE TRUE)
# hunter_add_package(fmt)

hunter_add_package(spdlog)
hunter_add_package(Boost COMPONENTS system)
hunter_add_package(nlohmann_json)
find_package(nlohmann_json REQUIRED CONFIG)
find_package(Boost REQUIRED COMPONENTS system CONFIG)
find_package(fmt REQUIRED CONFIG)
find_package(spdlog CONFIG REQUIRED CONFIG)
find_package(CUDA REQUIRED)
find_package(NvidiaML REQUIRED)

# Disable extended variants of C++ dialects
# i.e. don't choose gnu++17 over c++17
set(CMAKE_CXX_EXTENSIONS OFF)

# CUDA flags
set(CMAKE_CUDA_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# CMake FindCUDA auto seems to add unsupported architectures somtimes, so we allow the user
# to override with NVCC_ARCH_FLAGS
if(CUDA_MULTI_ARCH)
  CUDA_SELECT_NVCC_ARCH_FLAGS(CUDA_ARCH_FLAGS All)
else()
  if (DEFINED NVCC_ARCH_FLAGS)
    message(STATUS "Manual cuda arch flags...")
    CUDA_SELECT_NVCC_ARCH_FLAGS(CUDA_ARCH_FLAGS ${NVCC_ARCH_FLAGS})
  else()
    message(STATUS "Automatic cuda arch flags...")
    CUDA_SELECT_NVCC_ARCH_FLAGS(CUDA_ARCH_FLAGS Auto)
  endif()
endif()

SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wshadow -Wpedantic")

LIST(APPEND CMAKE_CUDA_FLAGS ${CUDA_ARCH_FLAGS}
					         -Wno-deprecated-gpu-targets
					         -lineinfo
					         --expt-extended-lambda
)

message(STATUS "Enabling CUDA support (version: ${CUDA_VERSION_STRING},"
			   " archs: ${CUDA_ARCH_FLAGS_readable})")

set(CUDA_ATTACH_VS_BUILD_RULE_TO_CUDA_FILE OFF)
set(CUDA_USE_STATIC_CUDA_RUNTIME ON)
set(CUDA_VERBOSE_BUILD OFF)


set(CPP_SOURCES
  src/profiler.cpp
  src/logger.cpp
  src/cupti_activity.cpp
  src/cupti_driver_cbid.cpp
  src/cupti_runtime_cbid.cpp
  src/nvml.cpp
  src/record.cpp
  src/record_writer.cpp
)

add_library(openvprof SHARED ${CPP_SOURCES} ${CUDA_SOURCES})

# Add include directories
target_include_directories(openvprof
  PRIVATE include/
  PRIVATE ${PROJECT_BINARY_DIR}/include
)
target_include_directories(openvprof SYSTEM
  PRIVATE third_party/
  PRIVATE ${CUDA_INCLUDE_DIRS}
  PRIVATE ${CUDA_TOOLKIT_ROOT_DIR}/extras/CUPTI/include
  PRIVATE ${Boost_INCLUDE_DIRS}
)



# target_link_libraries(openvprof fmt::fmt)
target_link_libraries(openvprof spdlog::spdlog)
target_link_libraries(openvprof ${CUDA_LIBRARIES})
target_link_libraries(openvprof Boost::boost Boost::system)
target_link_libraries(openvprof -L${CUDA_TOOLKIT_ROOT_DIR}/extras/CUPTI/lib64 cupti)
target_link_libraries(openvprof ${NvidiaML_LIBRARIES})
target_link_libraries(openvprof cuda)
target_link_libraries(openvprof "-Wl,--no-undefined")

add_executable(vec examples/samples/vectorAdd/vectorAdd.cu)
add_executable(um examples/samples/unified_memory/um.cu)
target_link_libraries(um cuda)

target_compile_definitions(openvprof PUBLIC -DPROJECT_NAME=openvprof)
set_target_properties(openvprof PROPERTIES
	# CUDA_SEPARABLE_COMPILATION ON
	CUDA_RESOLVE_DEVICE_SYMBOLS ON
)

# Request that scope be built with -std=c++11
# As this is a public compile feature anything that links to
# scope will also build with -std=c++11
target_compile_features(openvprof PUBLIC cxx_std_11)

git_get_head_revision(GIT_REFSPEC GIT_HASH)
git_local_changes(GIT_LOCAL_CHANGES)
message(STATUS GIT_REFSPEC=${GIT_REFSPEC})
message(STATUS GIT_HASH=${GIT_HASH})
message(STATUS GIT_LOCAL_CHANGES=${GIT_LOCAL_CHANGES})

# Convert CUDA flags from list
message(STATUS "CMAKE_CUDA_FLAGS: ${CMAKE_CUDA_FLAGS}")
string(REPLACE ";" " " CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS}")
message(STATUS "CMAKE_CUDA_FLAGS: ${CMAKE_CUDA_FLAGS}")

# Generate version file
configure_file (
    "${PROJECT_SOURCE_DIR}/include/openvprof/config.hpp.in"
    "${PROJECT_BINARY_DIR}/include/openvprof/config.hpp"
)

if(APPLE)
  # We need to add the path to the driver (libcuda.dylib) as an rpath,
  # so that the static cuda runtime can find it at runtime.
  set_property(TARGET scope
               PROPERTY
               BUILD_RPATH ${CMAKE_CUDA_IMPLICIT_LINK_DIRECTORIES})
endif()

# Add a special target to clean nvcc generated files.
CUDA_BUILD_CLEAN_TARGET()
