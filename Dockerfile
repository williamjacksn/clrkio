FROM python:3.8.1-alpine3.11

COPY requirements.txt /clrkio/requirements.txt

RUN /usr/local/bin/pip install --no-cache-dir --requirement /clrkio/requirements.txt

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/clrkio/run.py"]

COPY . /clrkio
