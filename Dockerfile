FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS builder

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv "${VIRTUAL_ENV}" \
    && pip install --no-cache-dir ".[app]"

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS runtime

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 shipguard \
    && useradd --uid 10001 --gid shipguard --no-create-home \
        --shell /usr/sbin/nologin shipguard

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["shipguard", "webhook", "--host", "0.0.0.0", "--port", "8000"]
