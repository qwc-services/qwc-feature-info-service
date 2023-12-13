# Ubuntu image has locales, which we want e.g. for psql client_encoding or info formatting
FROM sourcepole/qwc-uwsgi-base:ubuntu-v2023.10.26

ADD requirements.txt /srv/qwc_service/requirements.txt

# git: Required for pip with git repos
# postgresql-dev g++ python3-dev: Required for psycopg2
RUN \
    apt-get update && \
    apt-get install -y libpq-dev g++ python3-dev && \
    python3 -m pip install --no-cache-dir -r /srv/qwc_service/requirements.txt && \
    apt-get purge -y libpq-dev g++ python3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ADD src /srv/qwc_service/

ENV SERVICE_MOUNTPOINT=/api/v1/feature-info
