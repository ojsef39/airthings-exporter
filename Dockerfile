FROM alpine:latest
WORKDIR /
RUN apk update && apk upgrade && apk add --update bash

ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python
RUN python3 -m ensurepip
RUN pip3 install --no-cache --upgrade pip setuptools

RUN pip install airthings-exporter

EXPOSE 8000/tcp
ENTRYPOINT airthings-exporter --client-id $client_id --client-secret $client_secret --device-id $device_id
