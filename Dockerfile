FROM python:3.12.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
USER 10001:10001
EXPOSE 8000
# One process keeps the in-memory Prometheus registry correct; threads handle concurrency.
# Scale with pods, not Gunicorn workers, unless multiprocess metrics are configured.
CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=1", "--threads=4", "--worker-tmp-dir=/tmp", "--timeout=15", "app.main:create_app()"]
