#include "TelemetryServer.h"
#include <arpa/inet.h>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <chrono>
#include <thread>

TelemetryServer::TelemetryServer(BatteryState& state,
                                  BmsStateMachine& fsm, int port)
    : state_(state), fsm_(fsm), port_(port) {}

TelemetryServer::~TelemetryServer() { stop(); }

void TelemetryServer::start() {
    server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons(static_cast<uint16_t>(port_));
    addr.sin_addr.s_addr = INADDR_ANY;
    bind(server_fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
    listen(server_fd_, 1);

    running_ = true;
    accept_thread_ = std::thread([this]{ accept_loop(); });
}

void TelemetryServer::stop() {
    running_ = false;
    if (server_fd_ >= 0) { shutdown(server_fd_, SHUT_RDWR); close(server_fd_); server_fd_ = -1; }
    if (accept_thread_.joinable()) accept_thread_.join();
}

void TelemetryServer::accept_loop() {
    while (running_) {
        sockaddr_in client_addr{};
        socklen_t len = sizeof(client_addr);
        int cfd = accept(server_fd_, reinterpret_cast<sockaddr*>(&client_addr), &len);
        if (cfd < 0) break;
        serve_client(cfd);
        close(cfd);
    }
}

void TelemetryServer::send_telemetry(int fd) {
    char buf[256];
    BatteryState snap;
    BmsState     st;
    FaultCode    fc;
    {
        std::lock_guard lock(state_mu_);
        snap = state_;
        st   = fsm_.state();
        fc   = fsm_.fault_code();
    }
    auto ts = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
    int n = std::snprintf(buf, sizeof(buf),
        "{\"ts_us\":%lld,\"SoC\":%.4f,\"V_terminal\":%.4f,"
        "\"I_load\":%.2f,\"T_cell\":%.2f,\"V_RC\":%.6f,"
        "\"state\":\"%s\",\"fault_code\":\"%s\"}\n",
        (long long)ts,
        snap.soc, snap.v_terminal, snap.i_load, snap.t_cell, snap.v_rc,
        bms_state_name(st), fault_code_name(fc));
    send(fd, buf, n, MSG_NOSIGNAL);
}

void TelemetryServer::handle_command(const char* line, int fd) {
    // Simple keyword parser — avoids a JSON library dependency
    std::string s(line);
    auto extract_str = [&](const char* key) -> std::string {
        auto pos = s.find(key);
        if (pos == std::string::npos) return {};
        auto q1 = s.find('"', pos + strlen(key));
        auto q2 = s.find('"', q1 + 1);
        if (q1 == std::string::npos || q2 == std::string::npos) return {};
        return s.substr(q1 + 1, q2 - q1 - 1);
    };
    auto extract_num = [&](const char* key) -> double {
        auto pos = s.find(key);
        if (pos == std::string::npos) return 0.0;
        auto col = s.find(':', pos + strlen(key));
        if (col == std::string::npos) return 0.0;
        return std::stod(s.substr(col + 1));
    };

    std::string cmd = extract_str("\"command\"");
    std::lock_guard lock(state_mu_);

    if (cmd == "SET_CURRENT") {
        double val = extract_num("\"value\"");
        state_.i_load = val;
    } else if (cmd == "SET_FAULT") {
        std::string val = extract_str("\"value\"");
        if (val == "THERMAL_RUNAWAY") state_.block_cooling = true;
    } else if (cmd == "RESET") {
        fsm_.reset(state_);
    }
    (void)fd;
}

void TelemetryServer::serve_client(int cfd) {
    // Recv thread reads commands
    std::thread recv_t([this, cfd] {
        char line[512];
        std::string buf;
        char c;
        while (running_) {
            ssize_t n = recv(cfd, &c, 1, 0);
            if (n <= 0) break;
            if (c == '\n') {
                handle_command(buf.c_str(), cfd);
                buf.clear();
            } else {
                buf += c;
            }
        }
    });

    // Send loop at 100 Hz
    using namespace std::chrono;
    auto next = steady_clock::now();
    while (running_) {
        next += milliseconds(10);
        send_telemetry(cfd);
        std::this_thread::sleep_until(next);
    }
    recv_t.detach();
}
