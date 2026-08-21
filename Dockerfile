FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/home/ezeus
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir --upgrade "pip>=26.1.2" \
    && pip install --no-cache-dir .
RUN addgroup --system ezeus && adduser --system --ingroup ezeus --home /home/ezeus ezeus \
    && mkdir -p /home/ezeus \
    && chown -R ezeus:ezeus /app /home/ezeus
USER ezeus
CMD ["sh", "-c", "uvicorn apps.api.main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-8080} --log-level ${APP_LOG_LEVEL:-INFO}"]
