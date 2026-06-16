# Container image for hosts that deploy from a Dockerfile (Fly, Railway, etc.).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent SQLite location — mount a volume at /data on your host.
ENV NEWSTEXTER_DB=/data/newstexter.db
EXPOSE 8000

CMD ["sh", "-c", "uvicorn newstexter.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
