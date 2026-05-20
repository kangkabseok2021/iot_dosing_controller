cmake_minimum_required(VERSION 3.20)
project(ev_battery_hil_bms CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Threads REQUIRED)

add_library(bms_core STATIC
    src/BatteryModel.cpp
    src/BmsStateMachine.cpp
)
target_include_directories(bms_core PUBLIC src)
target_compile_options(bms_core PRIVATE -Wall -Wextra -Wpedantic)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux" OR CMAKE_SYSTEM_NAME STREQUAL "Darwin")
    add_executable(bms_daemon
        src/TelemetryServer.cpp
        src/main.cpp
    )
    target_link_libraries(bms_daemon PRIVATE bms_core Threads::Threads)
    target_compile_options(bms_daemon PRIVATE -Wall -Wextra)

    if(ENABLE_ASAN)
        target_compile_options(bms_daemon PRIVATE -fsanitize=address,undefined)
        target_link_options(bms_daemon PRIVATE -fsanitize=address,undefined)
    endif()
endif()

enable_testing()
if(BUILD_TESTING)
    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.tar.gz
        URL_HASH SHA256=8ad598c73ad796e0d8280b082cebd82a630d73e73cd3c70057938a6501bba5d7
        DOWNLOAD_EXTRACT_TIMESTAMP NEW
    )
    set(INSTALL_GTEST OFF)
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)

    add_executable(test_bms tests/test_bms.cpp)
    target_link_libraries(test_bms PRIVATE bms_core GTest::gtest_main)
    target_compile_options(test_bms PRIVATE -Wall -Wextra)
    add_test(NAME bms_tests COMMAND test_bms)
endif()
