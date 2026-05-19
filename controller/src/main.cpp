#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>

#include "DosingFsm.h"
#include "FlowSensor.h"
#include "ModbusServer.h"
#include "RfidSimulator.h"

int main() {
    const char* port_env = std::getenv("MODBUS_PORT");
    int port = port_env ? std::atoi(port_env) : 5502;

    ModbusServer modbus(port);
    if (!modbus.start())
        std::cerr << "Warning: Modbus stub — no libmodbus\n";

    RfidSimulator rfid;
    FlowSensor    flow;
    DosingFsm     fsm(1000.0);  // 1 L target

    auto last = std::chrono::steady_clock::now();
    std::cout << "IoT Dosing Controller running on port " << port << "\n";

    while (true) {
        auto now = std::chrono::steady_clock::now();
        double dt_s = std::chrono::duration<double>(now - last).count();
        last = now;

        auto tag       = rfid.scan();
        auto flow_read = flow.read(fsm.state() == DosingState::DOSING ? 200.0 : 0.0);
        bool valve     = modbus.get_valve_cmd();
        bool reset     = modbus.get_reset_cmd();

        fsm.update(valve, reset, flow_read, tag, dt_s);

        modbus.set_flow_rate(flow_read.flow_rate_ml_min);
        modbus.set_valve_state(valve);
        modbus.set_total_volume(static_cast<uint32_t>(fsm.accumulated_ml()));
        modbus.set_rfid_tag(tag ? tag->epc : "");
        modbus.set_dosing_state(fsm.state());

        std::cout << "[" << dosing_state_name(fsm.state()) << "] "
                  << "flow=" << flow_read.flow_rate_ml_min << " ml/min "
                  << "vol=" << fsm.accumulated_ml() << " ml\n";

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}
