FROM debian:bookworm-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake g++ libmodbus-dev pkg-config ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target dosing_daemon

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmodbus5 && rm -rf /var/lib/apt/lists/*
RUN useradd --system --no-create-home dosing
COPY --from=builder /src/build/dosing_daemon /usr/local/bin/dosing_daemon
USER dosing
EXPOSE 5502
CMD ["dosing_daemon"]
