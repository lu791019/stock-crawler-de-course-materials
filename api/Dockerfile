# API 專用 image（手冊17）：與根目錄 Dockerfile 同一套 uv 基底，差別只在最後的 CMD——
# worker image 跑 celery、這顆跑 uvicorn。build 時的 context 是專案根目錄：
#   docker build -f api/Dockerfile -t stock-api:latest .
FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y curl ca-certificates

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

RUN uv python install 3.11

RUN mkdir /crawler
COPY . /crawler/
WORKDIR /crawler/

RUN uv sync --frozen

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# 對外開 8000；--host 0.0.0.0 才收得到容器外的請求（不開 --reload：上線模式）
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
