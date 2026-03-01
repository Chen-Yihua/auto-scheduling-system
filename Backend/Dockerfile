FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        chromium chromium-driver \
        libglib2.0-0 libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxi6 \
        libxtst6 libxss1 libgtk-3-0 libatk1.0-0 libatk-bridge2.0-0 \
        libasound2 fonts-liberation ca-certificates && \
    rm -rf /var/lib/apt/lists/*
    
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/lib/chromium/chromedriver

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"


COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]