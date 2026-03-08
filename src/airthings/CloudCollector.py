import logging
from datetime import datetime, timedelta, timezone

import requests
from prometheus_client.metrics_core import GaugeMetricFamily
from prometheus_client.registry import Collector

# Timeout for API requests (in seconds)
REQUEST_TIMEOUT = 30

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class RateLimitException(Exception):
    """Custom exception for rate limiting with retry information."""

    def __init__(self, retry_after_seconds, retry_after_time):
        self.retry_after_seconds = retry_after_seconds
        self.retry_after_time = retry_after_time
        super().__init__(f"Rate limited until {retry_after_time}")


class CloudCollector(Collector):
    def __init__(self, client_id, client_secret, device_id_list):
        self.client_id = client_id
        self.client_secret = client_secret
        self.device_id_list = device_id_list
        self.rate_limit_until = None  # Track when rate limit expires

    def describe(self):
        """Return metric descriptors without making API calls.

        This is called during registration and should not make any external calls.
        """
        # Return empty list to allow registration to succeed
        # The actual metrics will be generated in collect()
        return []

    def collect(self):
        # Check if we're still rate limited
        if self.rate_limit_until:
            now = datetime.now(timezone.utc)
            if now < self.rate_limit_until:
                time_remaining = self.rate_limit_until - now
                seconds = int(time_remaining.total_seconds())

                # Format time remaining in human-readable form
                if seconds >= 3600:
                    hours = seconds // 3600
                    minutes = (seconds % 3600) // 60
                    time_str = f"{hours}h {minutes}m"
                elif seconds >= 60:
                    minutes = seconds // 60
                    secs = seconds % 60
                    time_str = f"{minutes}m {secs}s"
                else:
                    time_str = f"{seconds}s"

                logger.warning(
                    "⏳ Rate limited. Retry after: %s (in %s)",
                    self.rate_limit_until.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    time_str,
                )
                # Don't raise exception - just return empty metrics
                # This allows Prometheus default metrics to still be returned
                yield GaugeMetricFamily("airthings_gauge", "Airthings sensor values")
                return

            logger.info("✅ Rate limit window expired, resuming normal operation")
            self.rate_limit_until = None

        gauge_metric_family = GaugeMetricFamily("airthings_gauge", "Airthings sensor values")

        access_token = self.__get_access_token__()
        for device_id in self.device_id_list:
            data = self.__get_cloud_data__(access_token, device_id)
            self.__add_samples__(gauge_metric_family, data, device_id)

        yield gauge_metric_family

    def __add_samples__(self, gauge_metric_family, data, device_id):
        labels = {"device_id": device_id}
        if "battery" in data:
            gauge_metric_family.add_sample(
                "airthings_battery_percent", value=data["battery"], labels=labels
            )
        if "co2" in data:
            gauge_metric_family.add_sample(
                "airthings_co2_parts_per_million", value=data["co2"], labels=labels
            )
        if "humidity" in data:
            gauge_metric_family.add_sample(
                "airthings_humidity_percent", value=data["humidity"], labels=labels
            )
        if "pm1" in data:
            gauge_metric_family.add_sample(
                "airthings_pm1_micrograms_per_cubic_meter", value=float(data["pm1"]), labels=labels
            )
        if "pm25" in data:
            gauge_metric_family.add_sample(
                "airthings_pm25_micrograms_per_cubic_meter",
                value=float(data["pm25"]),
                labels=labels,
            )
        if "pressure" in data:
            gauge_metric_family.add_sample(
                "airthings_pressure_hectopascals", value=float(data["pressure"]), labels=labels
            )
        if "radonShortTermAvg" in data:
            gauge_metric_family.add_sample(
                "airthings_radon_short_term_average_becquerels_per_cubic_meter",
                value=float(data["radonShortTermAvg"]),
                labels=labels,
            )
        if "temp" in data:
            gauge_metric_family.add_sample(
                "airthings_temperature_celsius", value=data["temp"], labels=labels
            )
        if "voc" in data:
            gauge_metric_family.add_sample(
                "airthings_voc_parts_per_billion", value=data["voc"], labels=labels
            )

    def __get_cloud_data__(self, access_token, device_id):
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"https://ext-api.airthings.com/v1/devices/{device_id}/latest-samples",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        # Check for rate limiting
        if response.status_code == 429:
            self.__handle_rate_limit__(response, f"device {device_id}")

        response.raise_for_status()
        json_data = response.json()

        if "data" not in json_data:
            logger.error("Unexpected API response for device %s: %s", device_id, json_data)
            raise KeyError("'data' key not found in API response")

        return json_data["data"]

    def __get_access_token__(self):
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "read:device:current_values",
        }
        token_response = requests.post(
            "https://accounts-api.airthings.com/v1/token", data=data, timeout=REQUEST_TIMEOUT
        )

        # Check for rate limiting on token endpoint
        if token_response.status_code == 429:
            self.__handle_rate_limit__(token_response, "auth token")

        token_response.raise_for_status()
        return token_response.json()["access_token"]

    def __handle_rate_limit__(self, response, context):
        """Handle 429 rate limit response and parse Retry-After header."""
        # The API provides multiple rate limit headers:
        # - X-RateLimit-Reset: Unix timestamp when the rate limit window resets (most reliable)
        # - X-RateLimit-Retry-After: Seconds until reset (often buggy, returns 0)
        # - X-RateLimit-Remaining: How many requests are left (0 when rate limited)

        reset_header = response.headers.get("X-RateLimit-Reset")
        retry_after_header = response.headers.get("X-RateLimit-Retry-After")
        remaining_header = response.headers.get("X-RateLimit-Remaining")

        logger.info(
            "Rate limit hit (%s): Remaining=%s, Reset=%s, Retry-After=%s",
            context,
            remaining_header,
            reset_header,
            retry_after_header,
        )

        # Prefer X-RateLimit-Reset (Unix timestamp) as it's more reliable
        if reset_header:
            try:
                reset_timestamp = int(reset_header)
                self.rate_limit_until = datetime.fromtimestamp(reset_timestamp, tz=timezone.utc)
                logger.info("Using X-RateLimit-Reset header: %s", self.rate_limit_until)
            except (ValueError, OSError) as e:
                logger.error("Could not parse X-RateLimit-Reset '%s': %s", reset_header, e)
                reset_header = None  # Fall back to retry-after

        # Fallback to X-RateLimit-Retry-After if X-RateLimit-Reset wasn't available
        if not reset_header and retry_after_header:
            try:
                # Try parsing as seconds first
                retry_after_seconds = int(retry_after_header)
                # If retry_after is 0 or negative, the API says rate limit is already expired
                if retry_after_seconds <= 0:
                    logger.warning(
                        "X-RateLimit-Retry-After is %s (buggy header). Defaulting to 15 minutes.",
                        retry_after_seconds,
                    )
                    retry_after_seconds = 900  # 15 minutes
                self.rate_limit_until = datetime.now(timezone.utc) + timedelta(
                    seconds=retry_after_seconds
                )
            except ValueError:
                # Try parsing as ISO timestamp
                try:
                    self.rate_limit_until = datetime.fromisoformat(
                        retry_after_header.replace("Z", "+00:00")
                    )
                except ValueError:
                    # Default to 15 minutes if we can't parse
                    logger.error("Could not parse Retry-After header: %s", retry_after_header)
                    self.rate_limit_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        elif not reset_header:
            # No headers at all, default to 15 minutes
            logger.warning("No rate limit headers found, defaulting to 15 minutes")
            self.rate_limit_until = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Calculate human-readable time until retry
        time_remaining = self.rate_limit_until - datetime.now(timezone.utc)
        seconds = int(time_remaining.total_seconds())

        if seconds >= 3600:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            time_str = f"{hours}h {minutes}m"
        elif seconds >= 60:
            minutes = seconds // 60
            secs = seconds % 60
            time_str = f"{minutes}m {secs}s"
        else:
            time_str = f"{seconds}s"

        logger.error(
            "🚫 Rate limit hit (%s). Retry after: %s (in %s)",
            context,
            self.rate_limit_until.strftime("%Y-%m-%d %H:%M:%S %Z"),
            time_str,
        )

        raise RateLimitException(
            int((self.rate_limit_until - datetime.now(timezone.utc)).total_seconds()),
            self.rate_limit_until,
        )
