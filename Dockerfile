FROM python:3.8.3-alpine3.11

COPY requirements.txt /clrkio/requirements.txt

RUN /sbin/apk add --no-cache --virtual .deps gcc musl-dev postgresql-dev \
 && /sbin/apk add --no-cache libpq \
 && /usr/local/bin/pip install --no-cache-dir --requirement /clrkio/requirements.txt \
 && /sbin/apk del --no-cache .deps

ENV APP_VERSION="2020.3" \
    PYTHONUNBUFFERED="1" \
    TZ="Etc/UTC"

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/clrkio/run.py"]

COPY . /clrkio
