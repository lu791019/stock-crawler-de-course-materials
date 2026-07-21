# 使用 Ubuntu 24.04 作為基礎映像檔（自帶 Python 3.12）
FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV UV_SYSTEM_PYTHON=1
ENV UV_BREAK_SYSTEM_PACKAGES=1

RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh && uv --version

RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - && \
    apt-get update -y && apt-get install google-cloud-sdk -y

RUN mkdir -p /opt/airflow

# 安裝 Airflow 2.10.4（含 constraints 鎖定所有依賴版本）
RUN uv pip install --system "apache-airflow[celery,google,docker,postgres]==2.10.4" \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.4/constraints-3.12.txt"

# 複製專案檔案
COPY pyproject.toml uv.lock README.md /opt/airflow/
COPY crawler /opt/airflow/crawler/
# COPY key.json /opt/airflow/key.json  # GCP 憑證，使用 GCP 時取消註解

# 安裝專案依賴（不含 dev dependencies）
RUN cd /opt/airflow && uv pip install --system -e . --no-deps 2>/dev/null; \
    uv pip install --system requests pandas loguru celery pymysql sqlalchemy==1.4.36

ENV AIRFLOW_HOME=/opt/airflow
# ENV GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/key.json
ENV LC_ALL=C.UTF-8 LANG=C.UTF-8 TZ=Asia/Taipei
WORKDIR /opt/airflow
