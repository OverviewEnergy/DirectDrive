FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates build-essential \
 && rm -rf /var/lib/apt/lists/*

# LJM native library.
RUN curl -fsSL -o /tmp/ljm.tar.gz \
      https://files.labjack.com/installers/LJM/Linux/x64/release/labjack_ljm_software_2020_03_30_x86_64.tar.gz \
 && tar -xzf /tmp/ljm.tar.gz -C /tmp \
 && cd /tmp/labjack_ljm_software_*/ && ./labjack_ljm_installer.run -- --no-restart-device-rules \
 && rm -rf /tmp/ljm*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ /app/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]
