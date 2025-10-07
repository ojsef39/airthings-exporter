# Airthings Exporter

Prometheus exporter for Airthings devices - exports air quality metrics (CO2, temperature, humidity, VOC, radon, particulate matter) from Airthings cloud API.

## Setup

1. Register your Airthings device to sync with the cloud following the instructions manual
2. Go to the [Airthings Integrations webpage](https://dashboard.airthings.com/integrations/api-integration) and create an API Client to obtain:
   - **Client ID** - The ID shown when you edit the API client
   - **Client Secret** - The secret from the API client
3. Get your device serial number(s) from the [Airthings Dashboard](https://dashboard.airthings.com) or the Airthings app:
   - **Device ID** - Your device serial number (e.g., 1234567890)

## Development

This project uses [devenv](https://devenv.sh) for development environment setup.

```bash
# Enter development environment
direnv allow  # or: devenv shell

# Available commands
d-run     # Run the exporter locally
d-test    # Run tests
d-lint    # Run linters
d-format  # Format code
```

### Running Locally

```bash
# Set environment variables
export AIRTHINGS_CLIENT_ID='your_client_id'
export AIRTHINGS_CLIENT_SECRET='your_client_secret'
export AIRTHINGS_DEVICE_ID='your_device_id'
export AIRTHINGS_PORT=8000  # optional, defaults to 8000

# Run the exporter
d-run

# Test it works
curl http://localhost:8000/metrics
```

## Docker Usage

### Using Docker Compose

```yaml
services:
  airthings-exporter:
    image: ghcr.io/ojsef39/airthings-exporter:latest
    container_name: airthings-exporter
    environment:
      client_id: YOUR_CLIENT_ID
      client_secret: YOUR_CLIENT_SECRET
      device_id: YOUR_DEVICE_ID
    ports:
      - "8000:8000"
    restart: unless-stopped
```

### Using Docker CLI

```bash
# Single device
docker run -d \
  --name airthings-exporter \
  -p 8000:8000 \
  -e client_id=YOUR_CLIENT_ID \
  -e client_secret=YOUR_CLIENT_SECRET \
  -e device_id=YOUR_DEVICE_ID \
  ghcr.io/ojsef39/airthings-exporter:latest

# Multiple devices
docker run -d \
  --name airthings-exporter \
  -p 8000:8000 \
  -e client_id=YOUR_CLIENT_ID \
  -e client_secret=YOUR_CLIENT_SECRET \
  -e device_id=DEVICE_ID_1 \
  -e device_id=DEVICE_ID_2 \
  ghcr.io/ojsef39/airthings-exporter:latest
```

## Kubernetes Deployment

### Using a Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: airthings-credentials
  namespace: monitoring
type: Opaque
stringData:
  client-id: "YOUR_CLIENT_ID"
  client-secret: "YOUR_CLIENT_SECRET"
  device-id: "YOUR_DEVICE_ID"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: airthings-exporter
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: airthings-exporter
  template:
    metadata:
      labels:
        app: airthings-exporter
    spec:
      containers:
        - name: airthings-exporter
          image: ghcr.io/ojsef39/airthings-exporter:latest
          ports:
            - containerPort: 8000
              name: metrics
          env:
            - name: client_id
              valueFrom:
                secretKeyRef:
                  name: airthings-credentials
                  key: client-id
            - name: client_secret
              valueFrom:
                secretKeyRef:
                  name: airthings-credentials
                  key: client-secret
            - name: device_id
              valueFrom:
                secretKeyRef:
                  name: airthings-credentials
                  key: device-id
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "100m"
          livenessProbe:
            httpGet:
              path: /metrics
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 60
          readinessProbe:
            httpGet:
              path: /metrics
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
---
apiVersion: v1
kind: Service
metadata:
  name: airthings-exporter
  namespace: monitoring
  labels:
    app: airthings-exporter
spec:
  type: ClusterIP
  ports:
    - port: 8000
      targetPort: 8000
      protocol: TCP
      name: metrics
  selector:
    app: airthings-exporter
```

### ServiceMonitor for Prometheus Operator

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: airthings-exporter
  namespace: monitoring
  labels:
    app: airthings-exporter
spec:
  selector:
    matchLabels:
      app: airthings-exporter
  endpoints:
    - port: metrics
      interval: 5m
      scrapeTimeout: 30s
```

## Prometheus Configuration

```yaml
scrape_configs:
  - job_name: "airthings"
    scrape_interval: 5m
    scrape_timeout: 30s
    static_configs:
      - targets: ["airthings-exporter:8000"]
    # Optional: Relabel device IDs to human-readable names
    metric_relabel_configs:
      - source_labels: [device_id]
        regex: "1234567890"
        target_label: device_id
        replacement: "living_room"
      - source_labels: [device_id]
        regex: "0987654321"
        target_label: device_id
        replacement: "bedroom"
```

## Tested Devices

- Airthings View Plus
- Airthings Wave Mini

## API Limitations

⚠️ Airthings API for consumers allows only **120 requests per hour**. Each Prometheus scrape sends one request per device to the Airthings API.

**Recommended scrape interval:** 5 minutes (12 scrapes/hour per device)

## Metrics Exported

- `airthings_battery_percent` - Battery level
- `airthings_co2_parts_per_million` - CO2 concentration
- `airthings_humidity_percent` - Relative humidity
- `airthings_pm1_micrograms_per_cubic_meter` - PM1 particulate matter
- `airthings_pm25_micrograms_per_cubic_meter` - PM2.5 particulate matter
- `airthings_pressure_hectopascals` - Air pressure
- `airthings_radon_short_term_average_becquerels_per_cubic_meter` - Radon level
- `airthings_temperature_celsius` - Temperature
- `airthings_voc_parts_per_billion` - Volatile Organic Compounds

All metrics include a `device_id` label.
