#pragma once
#include "BmsStateMachine.h"
#include <atomic>
#include <mutex>
#include <thread>

// TCP telemetry server on port 5555.
// Broadcasts a JSON frame every 10 ms (100 Hz) to one connected client.
// Receives line-delimited JSON commands on the same connection.
//
// Protocol (both directions):
//   Telemetry: {"ts_us":..,"SoC":..,"V_terminal":..,"I_load":..,"T_cell":..,
//               "V_RC":..,"state":"DISCHARGING","fault_code":"NONE"}\n
//   Commands:  {"command":"SET_CURRENT","value":50.0}\n
//              {"command":"SET_FAULT","value":"THERMAL_RUNAWAY"}\n
//              {"command":"RESET"}\n
class TelemetryServer {
public:
    explicit TelemetryServer(BatteryState& state,
                              BmsStateMachine& fsm,
                              int port = 5555);
    ~TelemetryServer();

    void start();
    void stop();

private:
    void accept_loop();
    void serve_client(int client_fd);
    void send_telemetry(int fd);
    void handle_command(const char* line, int fd);

    BatteryState&    state_;
    BmsStateMachine& fsm_;
    int              port_;
    int              server_fd_{-1};

    std::atomic<bool> running_{false};
    std::thread       accept_thread_;
    mutable std::mutex state_mu_;   // guards state_ reads/writes from TCP thread
};
