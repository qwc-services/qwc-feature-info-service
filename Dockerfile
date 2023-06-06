# Ubuntu image has locales, which we want e.g. for psql client_encoding or info formatting
FROM sourcepole/qwc-uwsgi-base:ubuntu-v2023.05.12

ADD . /srv/qwc_service

# git: Required for pip with git repos
# postgresql-dev g++ python3-dev: Required for psycopg2
RUN \
    apt-get update && \
    apt-get install -y libpq-dev g++ python3-dev && \
    python3 -m pip install --no-cache-dir -r /srv/qwc_service/requirements.txt && \
    apt-get purge -y libpq-dev g++ python3-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV SERVICE_MOUNTPOINT=/api/v1/feature-info

# Default locale is en_US.utf8
# RUN localedef -i de_CH -c -f UTF-8 -A /usr/share/locale/locale.alias de_CH.UTF-8
# ENV LANG de_CH.utf8
