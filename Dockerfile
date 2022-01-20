FROM python:3.10.2-alpine3.15

COPY requirements.txt /clrkio/requirements.txt

RUN /sbin/apk add --no-cache libpq
RUN /usr/local/bin/pip install --no-cache-dir --requirement /clrkio/requirements.txt

ENV APP_VERSION="2021.1" \
    PYTHONUNBUFFERED="1" \
    TZ="Etc/UTC"

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/clrkio/run.py"]

COPY . /clrkio
