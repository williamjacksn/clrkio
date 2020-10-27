FROM python:3.9.0-alpine3.12

COPY requirements.txt /clrkio/requirements.txt

RUN /sbin/apk add --no-cache libpq
RUN /usr/local/bin/pip install --no-cache-dir --requirement /clrkio/requirements.txt

ENV APP_VERSION="2020.4" \
    PYTHONUNBUFFERED="1" \
    TZ="Etc/UTC"

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/clrkio/run.py"]

COPY . /clrkio
