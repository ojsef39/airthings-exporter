import time
from unittest.mock import Mock, patch

import pytest
import requests
from prometheus_client import REGISTRY, start_http_server

from airthings.CloudCollector import CloudCollector


class TestIntegration:
    @pytest.fixture
    def mock_http_server(self):
        """Start a test HTTP server for Prometheus metrics."""
        port = 18000
        start_http_server(port)
        yield f"http://localhost:{port}"
        # Server cleanup happens automatically

    @pytest.fixture
    def mock_collector(self, mock_client_credentials, mock_device_id):
        """Create a mock collector for testing."""
        collector = CloudCollector(
            mock_client_credentials["client_id"],
            mock_client_credentials["client_secret"],
            [mock_device_id],
        )
        return collector

    def test_metrics_endpoint(
        self,
        mock_http_server,
        mock_device_data,
        mock_access_token,
    ):
        """Test that metrics endpoint returns Prometheus-formatted metrics."""
        # Give server time to start
        time.sleep(0.5)

        # Fetch metrics from the server (using real requests, not mocked)
        import requests as real_requests

        response = real_requests.get(f"{mock_http_server}/metrics", timeout=5)

        assert response.status_code == 200
        assert "text/plain" in response.headers.get("Content-Type", "")

        # Verify Prometheus format
        content = response.text
        assert "# HELP" in content
        assert "# TYPE" in content

    @patch("requests.post")
    @patch("requests.get")
    def test_collector_integration(
        self, mock_get, mock_post, mock_device_data, mock_access_token, mock_device_id
    ):
        """Test CloudCollector integration with Prometheus client."""
        # Setup mocks
        mock_post.return_value.json.return_value = {"access_token": mock_access_token}
        mock_get.return_value.json.return_value = {"data": mock_device_data}

        # Create and register collector
        collector = CloudCollector("client_id", "client_secret", [mock_device_id])
        REGISTRY.register(collector)

        try:
            # Collect metrics
            metrics = list(collector.collect())

            assert len(metrics) > 0
            gauge = metrics[0]
            samples = list(gauge.samples)

            # Verify metric names
            sample_names = [s.name for s in samples]
            assert "airthings_temperature_celsius" in sample_names
            assert "airthings_humidity_percent" in sample_names

            # Verify values match mock data
            temp_sample = next(s for s in samples if s.name == "airthings_temperature_celsius")
            assert temp_sample.value == mock_device_data["temp"]
            assert temp_sample.labels["device_id"] == mock_device_id

        finally:
            # Cleanup: unregister collector
            REGISTRY.unregister(collector)

    @patch("requests.post")
    def test_api_error_handling(self, mock_post, mock_device_id):
        """Test handling of API errors - should raise exception to be caught by HTTP handler."""
        # Simulate API error
        mock_post.side_effect = requests.exceptions.RequestException("API Error")

        collector = CloudCollector("client_id", "client_secret", [mock_device_id])

        # Should raise exception (to be caught by main.py and return 500)
        with pytest.raises(requests.exceptions.RequestException):
            list(collector.collect())

    @patch("requests.post")
    @patch("requests.get")
    def test_missing_data_fields(self, mock_get, mock_post, mock_access_token, mock_device_id):
        """Test collector handles missing data fields gracefully."""
        # Setup mocks with incomplete data
        mock_post.return_value.json.return_value = {"access_token": mock_access_token}
        mock_get.return_value.json.return_value = {"data": {"temp": 20.0}}  # Only temperature

        collector = CloudCollector("client_id", "client_secret", [mock_device_id])
        metrics = list(collector.collect())

        assert len(metrics) > 0
        samples = list(metrics[0].samples)
        sample_names = [s.name for s in samples]

        # Should have temperature but not other metrics
        assert "airthings_temperature_celsius" in sample_names
        assert "airthings_humidity_percent" not in sample_names
