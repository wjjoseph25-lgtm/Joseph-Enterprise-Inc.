FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python download_ephe.py

ENV PYTHONUNBUFFERED=1 \
    PORT=10000 \
    SWEPH_PATH=/app/ephe \
    REQUIRE_EPHE_FILES=true

EXPOSE 10000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-10000}\" --proxy-headers --forwarded-allow-ips=\"*\""]
