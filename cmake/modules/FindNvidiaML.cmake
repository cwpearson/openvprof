

find_path(NvidiaML_INCLUDE_DIR
    NAMES nvml.h
    PATHS ${CUDA_INCLUDE_DIRS}
    PATH_SUFFIXES Foo
)
find_library(NvidiaML_LIBRARY
    NAMES nvidia-ml
    PATHS "/usr/lib/nvidia-*"
    PATH_SUFFIXES lib
)

include(FindPackageHandleStandardArgs)
find_package_handle_standard_args(NvidiaML
  FOUND_VAR NvidiaML_FOUND
  REQUIRED_VARS
    NvidiaML_LIBRARY
    NvidiaML_INCLUDE_DIR
  VERSION_VAR NvidiaML_VERSION
)

if(NvidiaML_FOUND)
  set(NvidiaML_LIBRARIES ${NvidiaML_LIBRARY})
  set(NvidiaML_INCLUDE_DIRS ${NvidiaML_INCLUDE_DIR})
endif()