# Ubuntu image has locales, which we want e.g. for psql client_encoding or info formatting
FROM sourcepole/qwc-uwsgi-base:ubuntu-v2023.05.12

ADD . /srv/qwc_service

# git: Required for pip with git repos
# postgresql-dev g++ python3-dev: Required for psycopg2
RUN \
    apk add --no-cache --virtual runtime-deps postgresql-libs && \
    apk add --no-cache --virtual build-deps --update git postgresql-dev g++ python3-dev && \
    pip3 install --no-cache-dir -r /srv/qwc_service/requirements.txt && \
    apk del build-deps

ENV SERVICE_MOUNTPOINT=/api/v1/feature-info

# Default locale is en_US.utf8
# RUN localedef -i de_CH -c -f UTF-8 -A /usr/share/locale/locale.alias de_CH.UTF-8
# ENV LANG de_CH.utf8
