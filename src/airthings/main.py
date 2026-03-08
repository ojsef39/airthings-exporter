import argparse
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

from prometheus_client import REGISTRY, generate_latest

from airthings.CloudCollector import CloudCollector, RateLimitException

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(
    prog="airthings-exporter", description="Prometheus exporter for Airthings devices"
)
parser.add_argument("--client-id")
parser.add_argument("--client-secret")
parser.add_argument("--device-id", action="append")
parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
args = parser.parse_args()

# Create and register collector
collector = CloudCollector(args.client_id, args.client_secret, args.device_id)
REGISTRY.register(collector)

# Try initial API check to see if we're rate limited
try:
    list(collector.collect())
    logger.info("✅ Initial API check successful")
except RateLimitException as e:
    logger.warning("⚠️ Rate limited at startup (limited until %s)", e.retry_after_time)
except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("❌ Initial API check failed: %s", e)


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        elif self.path == "/metrics":
            try:
                output = generate_latest(REGISTRY)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.end_headers()
                self.wfile.write(output)
            except RateLimitException as e:
                self.send_response(429)
                self.send_header("Retry-After", str(e.retry_after_seconds))
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                message = f"Rate limited. Retry after {e.retry_after_time}"
                self.wfile.write(message.encode())
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Error generating metrics: {str(e)}".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *log_args):  # pylint: disable=arguments-differ
        # Only log errors, suppress normal HTTP logs to reduce noise
        if "code 4" in str(log_args) or "code 5" in str(log_args):
            logger.info(fmt, *log_args)


def main():
    server = HTTPServer(("", args.port), HealthCheckHandler)
    print(f"Now listening on port {args.port}")
    print("Endpoints: /metrics, /health")
    server.serve_forever()


if __name__ == "__main__":
    main()
