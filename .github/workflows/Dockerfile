FROM ubuntu:22.04

WORKDIR /app

COPY . /app

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Kyiv

RUN apt-get update && apt-get install -y --no-install-recommends \
    rsync \
    tzdata \
    python3 \
    python3-pip \
    curl \
    wget \
    bash \
    openssh-client \
    sshpass \
    && pip install requests \
    && mkdir -p /root/.ssh && \
    ssh-keyscan 185.216.21.120 >> /root/.ssh/known_hosts && \
    ssh-keyscan 185.216.21.212 >> /root/.ssh/known_hosts && \
    ssh-keyscan 62.169.159.201 >> /root/.ssh/known_hosts && \
    ssh-keyscan 185.216.22.230 >> /root/.ssh/known_hosts && \
    ssh-keyscan 185.216.22.135 >> /root/.ssh/known_hosts && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    chmod +x /app/monitoring.sh /app/fetch_metrics.sh /app/log_analyzer.py && \
    rm -rf /var/lib/apt/lists/*
 

CMD ["./monitoring_v2.sh"]
