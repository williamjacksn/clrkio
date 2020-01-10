FROM python:3.8.1-alpine3.11

COPY requirements.txt /clrkio/requirements.txt

RUN /sbin/apk add --no-cache --virtual .deps gcc musl-dev postgresql-dev \
 && /sbin/apk add --no-cache libpq \
 && /usr/local/bin/pip install --no-cache-dir --requirement /clrkio/requirements.txt \
 && /sbin/apk del --no-cache .deps

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/clrkio/run.py"]

COPY . /clrkio
