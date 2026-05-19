FROM python:3.12-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY api/ api/
COPY collector/ collector/
COPY plc_simulator/ plc_simulator/
COPY static/ static/
