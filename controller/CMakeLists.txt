cmake_minimum_required(VERSION 3.21)
project(iot_dosing_controller CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Threads REQUIRED)

# ── Optional libmodbus ─────────────────────────────────────────────────────
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
  pkg_check_modules(LIBMODBUS libmodbus)
endif()
if(LIBMODBUS_FOUND)
  message(STATUS "libmodbus found — building full Modbus TCP server")
  set(HAS_LIBMODBUS TRUE)
else()
  message(STATUS "libmodbus not found — building stub Modbus server")
  set(HAS_LIBMODBUS FALSE)
endif()

# ── GoogleTest ─────────────────────────────────────────────────────────────
include(FetchContent)
FetchContent_Declare(googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# ── Core library (no Modbus — always builds) ───────────────────────────────
add_library(dosing_core STATIC
  src/RfidSimulator.cpp
  src/FlowSensor.cpp
  src/DosingFsm.cpp
)
target_include_directories(dosing_core PUBLIC src)
target_link_libraries(dosing_core PUBLIC Threads::Threads)
if(MSVC)
  target_compile_options(dosing_core PRIVATE /W3)
else()
  target_compile_options(dosing_core PRIVATE -Wall -Wextra)
endif()

# ── ModbusServer library (conditional) ────────────────────────────────────
add_library(modbus_server STATIC src/ModbusServer.cpp)
target_include_directories(modbus_server PUBLIC src)
target_link_libraries(modbus_server PUBLIC dosing_core)
if(HAS_LIBMODBUS)
  target_compile_definitions(modbus_server PUBLIC HAS_LIBMODBUS)
  target_include_directories(modbus_server PUBLIC ${LIBMODBUS_INCLUDE_DIRS})
  target_link_libraries(modbus_server PUBLIC ${LIBMODBUS_LIBRARIES})
endif()

# ── Daemon ─────────────────────────────────────────────────────────────────
add_executable(dosing_daemon src/main.cpp)
target_link_libraries(dosing_daemon PRIVATE modbus_server)

# ── Tests (link only dosing_core — no Modbus needed) ──────────────────────
enable_testing()
add_executable(test_controller tests/test_controller.cpp)
target_link_libraries(test_controller PRIVATE dosing_core GTest::gtest_main)
include(GoogleTest)
gtest_discover_tests(test_controller)
