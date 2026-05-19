#pragma once
#include "DosingFsm.h"
#include <atomic>
#include <cstdint>
#include <string>
#include <thread>

// Modbus TCP server exposing sensor state and receiving PLC commands.
//
// Holding registers (read by PLC):
//   0: flow_rate_ml_min × 10  (uint16, fixed-point)
//   1: valve_state             (0=closed, 1=open)
//   2: total_volume_ml high    (uint16)
//   3: total_volume_ml low     (uint16)
//   4-11: rfid_epc             (8×uint16 = 16 ASCII bytes)
//   12: dosing_state           (0=IDLE,1=DOSING,2=PAUSE,3=COMPLETE)
//
// Coils (written by PLC):
//   0: valve_cmd  (0/1)
//   1: reset_cmd  (0/1)
class ModbusServer {
public:
    explicit ModbusServer(int port = 5502);
    ~ModbusServer();

    bool start();
    void stop();
    bool is_running() const { return running_.load(); }

    // Called by main loop to push sensor state into Modbus registers.
    void set_flow_rate(double ml_per_min);
    void set_valve_state(bool open);
    void set_total_volume(uint32_t ml);
    void set_rfid_tag(const std::string& epc_hex);
    void set_dosing_state(DosingState state);

    // Read PLC commands from Modbus coils.
    bool get_valve_cmd() const;
    bool get_reset_cmd() const;

private:
    int          port_;
    std::atomic<bool> running_{false};
    std::thread  server_thread_;

    // Shared register state (updated by main loop, read by Modbus thread)
    mutable std::mutex mu_;
    uint16_t regs_[13]{};  // 13 holding registers
    bool     coils_[2]{};  // valve_cmd, reset_cmd

    void serve_loop();
};
