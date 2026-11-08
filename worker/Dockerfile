# build from the repository root:  docker build -f worker/Dockerfile -t cmdparser-worker:1.0 .
FROM python:3.11.9-slim-bookworm
WORKDIR /app
COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY worker/ /app/
COPY prompts/ /app/prompts/
CMD ["python", "/app/worker.py"]
