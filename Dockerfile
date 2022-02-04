# Ubuntu image has locales, which we want e.g. for psql client_encoding or info formatting
FROM sourcepole/qwc-uwsgi-base:ubuntu-v2022.01.26

ADD . /srv/qwc_service

RUN pip3 install --no-cache-dir -r /srv/qwc_service/requirements.txt

ENV SERVICE_MOUNTPOINT=/api/v1/feature-info

# Default locale is en_US.utf8
# RUN localedef -i de_CH -c -f UTF-8 -A /usr/share/locale/locale.alias de_CH.UTF-8
# ENV LANG de_CH.utf8
