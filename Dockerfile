FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/home/ezeus
WORKDIR /app
ARG PIP_VERSION=26.2.1
ARG SETUPTOOLS_VERSION=84.0.0
ARG WHEEL_VERSION=0.48.0
RUN apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir \
      "pip==${PIP_VERSION}" \
      "setuptools==${SETUPTOOLS_VERSION}" \
      "wheel==${WHEEL_VERSION}" \
    && pip install --no-cache-dir --require-hashes -r requirements.lock
COPY apps ./apps
COPY connectors ./connectors
COPY core ./core
COPY infrastructure ./infrastructure
COPY plugins ./plugins
COPY scripts ./scripts
COPY tests/fixtures/invoice.pdf ./tests/fixtures/invoice.pdf
COPY webhooks ./webhooks
COPY alembic.ini ./
RUN pip install --no-cache-dir --no-deps --no-build-isolation . \
    && pip uninstall --yes pip setuptools wheel
RUN addgroup --system --gid 10001 ezeus \
    && adduser --system --uid 10001 --ingroup ezeus --home /home/ezeus ezeus \
    && mkdir -p /home/ezeus \
    && chown -R ezeus:ezeus /app /home/ezeus
USER ezeus
CMD ["python", "-m", "apps.api"]
