#include "ModbusServer.h"
#include <algorithm>
#include <cstring>
#include <iostream>
#include <mutex>

#ifdef HAS_LIBMODBUS
#include <modbus/modbus.h>
#endif

ModbusServer::ModbusServer(int port) : port_(port) {}

ModbusServer::~ModbusServer() { stop(); }

bool ModbusServer::start() {
#ifdef HAS_LIBMODBUS
    running_.store(true);
    server_thread_ = std::thread(&ModbusServer::serve_loop, this);
    return true;
#else
    std::cerr << "ModbusServer: libmodbus not compiled in (stub mode)\n";
    return false;
#endif
}

void ModbusServer::stop() {
    running_.store(false);
    if (server_thread_.joinable()) server_thread_.join();
}

void ModbusServer::set_flow_rate(double ml_per_min) {
    std::lock_guard<std::mutex> lk(mu_);
    regs_[0] = static_cast<uint16_t>(ml_per_min * 10.0);
}

void ModbusServer::set_valve_state(bool open) {
    std::lock_guard<std::mutex> lk(mu_);
    regs_[1] = open ? 1u : 0u;
}

void ModbusServer::set_total_volume(uint32_t ml) {
    std::lock_guard<std::mutex> lk(mu_);
    regs_[2] = static_cast<uint16_t>(ml >> 16);
    regs_[3] = static_cast<uint16_t>(ml & 0xFFFF);
}

void ModbusServer::set_rfid_tag(const std::string& epc_hex) {
    std::lock_guard<std::mutex> lk(mu_);
    // Pack 16 ASCII bytes into 8 uint16 registers (2 chars per register)
    for (int i = 0; i < 8; ++i) {
        uint16_t hi = (i * 2 < static_cast<int>(epc_hex.size())) ?
                      static_cast<uint16_t>(epc_hex[i * 2]) : 0;
        uint16_t lo = (i * 2 + 1 < static_cast<int>(epc_hex.size())) ?
                      static_cast<uint16_t>(epc_hex[i * 2 + 1]) : 0;
        regs_[4 + i] = (hi << 8) | lo;
    }
}

void ModbusServer::set_dosing_state(DosingState state) {
    std::lock_guard<std::mutex> lk(mu_);
    regs_[12] = static_cast<uint16_t>(state);
}

bool ModbusServer::get_valve_cmd() const {
    std::lock_guard<std::mutex> lk(mu_);
    return coils_[0];
}

bool ModbusServer::get_reset_cmd() const {
    std::lock_guard<std::mutex> lk(mu_);
    return coils_[1];
}

void ModbusServer::serve_loop() {
#ifdef HAS_LIBMODBUS
    modbus_t* ctx = modbus_new_tcp("0.0.0.0", port_);
    if (!ctx) { running_.store(false); return; }

    modbus_mapping_t* mb_map = modbus_mapping_new(8, 0, 13, 0);
    if (!mb_map) { modbus_free(ctx); running_.store(false); return; }

    int server_socket = modbus_tcp_listen(ctx, 1);
    if (server_socket < 0) {
        modbus_mapping_free(mb_map);
        modbus_free(ctx);
        running_.store(false);
        return;
    }

    // Non-blocking accept loop
    modbus_set_response_timeout(ctx, 0, 100'000);  // 100ms timeout

    while (running_.load()) {
        int client = modbus_tcp_accept(ctx, &server_socket);
        if (client < 0) continue;

        // Sync registers from shared state into mapping
        {
            std::lock_guard<std::mutex> lk(mu_);
            std::memcpy(mb_map->tab_registers, regs_, sizeof(regs_));
        }

        uint8_t query[MODBUS_TCP_MAX_ADU_LENGTH];
        int rc;
        while ((rc = modbus_receive(ctx, query)) >= 0 && running_.load()) {
            // Copy PLC coil writes into shared state
            {
                std::lock_guard<std::mutex> lk(mu_);
                coils_[0] = mb_map->tab_bits[0] != 0;
                coils_[1] = mb_map->tab_bits[1] != 0;
                std::memcpy(mb_map->tab_registers, regs_, sizeof(regs_));
            }
            modbus_reply(ctx, query, rc, mb_map);
        }
        close(client);
    }

    modbus_mapping_free(mb_map);
    modbus_close(ctx);
    modbus_free(ctx);
#endif
}
