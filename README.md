# Airthings Exporter

Docker container image for Prometheus exporter for Airthings devices.
Link to docker hub: https://hub.docker.com/r/dachack/airthings-exporter

## Setup

- Register your Airthings device to sync with the cloud following the instructions manual
- Check the Airthings app or the [web dashboard](https://dashboard.airthings.com) to obtain your device serial number. This is your client id
- Go to the [Airthings Integrations webpage](https://dashboard.airthings.com/integrations/api-integration) and request an API Client to obtain a client secret
- Run container in same virtual network as your Prometheus server(see below)

## Usage

```shell
  airthings-exporter:
    container_name: airthings-exporter
    image: dachack/airthings-exporter
    networks:
      - prometheus
    environment:
      client_id: YOUR_CLIENT_ID
      client_secret: YOUR_SECRET
      device_id: YOUR_DEVICE_ID
    restart: unless-stopped
```

Use the `--port` option have the exporter listen on a different port. Default port is 8000.

## Tested Devices

- Airthings View Plus
- Airthings Wave Mini

## Example Prometheus configuration file (prometheus.yml)

```yml
scrape_configs:
  - job_name: 'airthings'
    scrape_interval: 5m
    scrape_timeout: 10s
    static_configs:
      - targets: ['localhost:8000']
```

## API limitations

Airthings API for consumers allows only up to 120 requests per hour. Every scrape in prometheus sends one request per device to the Airthings API. Make sure the configured prometheus scrape interval does not exceed the limit.
