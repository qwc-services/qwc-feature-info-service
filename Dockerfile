# Ubuntu image has locales, which we want e.g. for psql client_encoding or info formatting
FROM sourcepole/qwc-uwsgi-base:ubuntu-v2026.01.06

WORKDIR /srv/qwc_service
ADD pyproject.toml uv.lock ./

# git: Required for pip with git repos
# postgresql-dev g++ python3-dev: Required for psycopg2
RUN \
    apt-get update && \
    apt-get install -y libpq-dev g++ python3-dev && \
    uv sync --frozen && \
    uv cache clean && \
    apt-get purge -y libpq-dev g++ python3-dev && \
    apt-get autoremove -y && \
    apt-get install -y libpq5 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ADD src /srv/qwc_service/

ENV SERVICE_MOUNTPOINT=/api/v1/feature-info
