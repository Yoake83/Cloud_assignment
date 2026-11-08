# build from the repository root:  docker build -f service/Dockerfile -t cmdparser-service:1.0 .
# No model weights are copied into this image; they are downloaded from object storage at start-up.
FROM python:3.11.9-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY service/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt && rm -rf /root/.cache
COPY service/*.py /app/
COPY data/schema.json /app/schema.json
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
