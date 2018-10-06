

macro(dir_glob result pattern)
FILE(GLOB children ${pattern})
SET(dirlist "")
FOREACH(child ${children})
  IF(IS_DIRECTORY ${child})
    LIST(APPEND dirlist ${child})
  ENDIF()
ENDFOREACH()
set(${result} ${dirlist})
endmacro()

set(DRIVER_PATHS "")
dir_glob(ADD_PATHS "/usr/lib/nvidia-*" )
list(APPEND DRIVER_PATHS ${ADD_PATHS})

find_path(NvidiaML_INCLUDE_DIR
    NAMES nvml.h
    PATHS ${CUDA_INCLUDE_DIRS}
)
find_library(NvidiaML_LIBRARY
    NAMES nvidia-ml
    PATHS ${DRIVER_PATHS}
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
  message(STATUS "Found nvidia-ml Libraries: " ${NvidiaML_LIBRARIES})
  message(STATUS "Found nvidia-ml Includes: "  ${NvidiaML_INCLUDE_DIRS})
endif()