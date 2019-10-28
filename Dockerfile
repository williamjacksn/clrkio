FROM python:3.8.0-alpine3.10

COPY requirements.txt /clrkio/requirements.txt

RUN /usr/local/bin/pip install --no-cache-dir --requirement /clrkio/requirements.txt

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/clrkio/run.py"]

COPY . /clrkio
