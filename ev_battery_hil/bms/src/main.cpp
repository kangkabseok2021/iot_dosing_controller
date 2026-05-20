#include "BmsStateMachine.h"
#include "TelemetryServer.h"
#include <chrono>
#include <csignal>
#include <iostream>
#include <thread>

static volatile bool g_stop = false;
static void on_signal(int) { g_stop = true; }

int main(int argc, char* argv[]) {
    int port = 5555;
    if (argc > 1) port = std::atoi(argv[1]);

    std::signal(SIGTERM, on_signal);
    std::signal(SIGINT,  on_signal);

    BatteryState    state;
    BmsStateMachine fsm;
    TelemetryServer server(state, fsm, port);

    server.start();
    std::cout << "BMS daemon listening on TCP :" << port << "\n";

    using namespace std::chrono;
    auto next = steady_clock::now();
    uint64_t tick = 0;

    while (!g_stop) {
        next += microseconds(1000);  // 1 kHz physics loop

        bool ok = fsm.update(state);
        if (!ok)
            std::cerr << "Command rejected: " << fsm.fault_detail() << "\n";

        if (fsm.state() == BmsState::FAULT && ++tick % 10000 == 0) {
            std::cerr << "[FAULT] " << fsm.fault_detail() << "\n";
        }

        std::this_thread::sleep_until(next);
    }

    server.stop();
    return 0;
}
