from unittest.mock import Mock, patch

import pytest
from prometheus_client.metrics_core import GaugeMetricFamily

from airthings.CloudCollector import CloudCollector


class TestCloudCollector:
    def test_init(self, mock_client_credentials, mock_device_id):
        """Test CloudCollector initialization."""
        collector = CloudCollector(
            mock_client_credentials["client_id"],
            mock_client_credentials["client_secret"],
            [mock_device_id],
        )
        assert collector.client_id == mock_client_credentials["client_id"]
        assert collector.client_secret == mock_client_credentials["client_secret"]
        assert collector.device_id_list == [mock_device_id]

    @patch("requests.post")
    def test_get_access_token(self, mock_post, mock_client_credentials, mock_access_token):
        """Test access token retrieval."""
        mock_post.return_value.json.return_value = {"access_token": mock_access_token}

        collector = CloudCollector(
            mock_client_credentials["client_id"],
            mock_client_credentials["client_secret"],
            ["device1"],
        )
        # Call the dunder method directly
        token = collector.__get_access_token__()

        assert token == mock_access_token
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://accounts-api.airthings.com/v1/token"
        assert call_args[1]["data"]["grant_type"] == "client_credentials"
        assert call_args[1]["data"]["client_id"] == mock_client_credentials["client_id"]
        assert call_args[1]["data"]["client_secret"] == mock_client_credentials["client_secret"]
        assert call_args[1]["timeout"] == 30

    @patch("requests.get")
    def test_get_cloud_data(self, mock_get, mock_access_token, mock_device_id, mock_device_data):
        """Test fetching cloud data for a device."""
        mock_get.return_value.json.return_value = {"data": mock_device_data}

        collector = CloudCollector("client_id", "client_secret", [mock_device_id])
        # Call the dunder method directly
        data = collector.__get_cloud_data__(mock_access_token, mock_device_id)

        assert data == mock_device_data
        mock_get.assert_called_once_with(
            f"https://ext-api.airthings.com/v1/devices/{mock_device_id}/latest-samples",
            headers={"Authorization": f"Bearer {mock_access_token}"},
            timeout=30,
        )

    def test_add_samples_all_metrics(self, mock_device_id, mock_device_data):
        """Test adding all available metrics to gauge."""
        collector = CloudCollector("client_id", "client_secret", [mock_device_id])
        gauge = GaugeMetricFamily("airthings_gauge", "Airthings sensor values")

        # Call the dunder method directly
        collector.__add_samples__(gauge, mock_device_data, mock_device_id)

        # Verify samples were added
        samples = list(gauge.samples)
        sample_names = [s.name for s in samples]

        expected_metrics = [
            "airthings_battery_percent",
            "airthings_co2_parts_per_million",
            "airthings_humidity_percent",
            "airthings_pm1_micrograms_per_cubic_meter",
            "airthings_pm25_micrograms_per_cubic_meter",
            "airthings_pressure_hectopascals",
            "airthings_radon_short_term_average_becquerels_per_cubic_meter",
            "airthings_temperature_celsius",
            "airthings_voc_parts_per_billion",
        ]

        for metric in expected_metrics:
            assert metric in sample_names

    def test_add_samples_partial_data(self, mock_device_id):
        """Test adding samples with partial device data."""
        collector = CloudCollector("client_id", "client_secret", [mock_device_id])
        gauge = GaugeMetricFamily("airthings_gauge", "Airthings sensor values")

        partial_data = {"temp": 21.5, "humidity": 50.0}
        # Call the dunder method directly
        collector.__add_samples__(gauge, partial_data, mock_device_id)

        samples = list(gauge.samples)
        sample_names = [s.name for s in samples]

        assert "airthings_temperature_celsius" in sample_names
        assert "airthings_humidity_percent" in sample_names
        assert "airthings_co2_parts_per_million" not in sample_names

    def test_add_samples_with_device_label(self, mock_device_id, mock_device_data):
        """Test that device_id is added as a label to metrics."""
        collector = CloudCollector("client_id", "client_secret", [mock_device_id])
        gauge = GaugeMetricFamily("airthings_gauge", "Airthings sensor values")

        # Call the dunder method directly
        collector.__add_samples__(gauge, mock_device_data, mock_device_id)

        samples = list(gauge.samples)
        for sample in samples:
            assert sample.labels["device_id"] == mock_device_id

    @patch("requests.post")
    @patch("requests.get")
    def test_collect(
        self,
        mock_get,
        mock_post,
        mock_access_token,
        mock_device_data,
    ):
        """Test the collect method."""
        mock_post.return_value.json.return_value = {"access_token": mock_access_token}
        mock_get.return_value.json.return_value = {"data": mock_device_data}

        device_ids = ["device1", "device2"]
        collector = CloudCollector("client_id", "client_secret", device_ids)
        metrics = list(collector.collect())

        assert len(metrics) == 1
        assert isinstance(metrics[0], GaugeMetricFamily)
        mock_post.assert_called_once()
        assert mock_get.call_count == len(device_ids)

    @patch("requests.post")
    @patch("requests.get")
    def test_collect_multiple_devices(
        self,
        mock_get,
        mock_post,
        mock_access_token,
        mock_device_data,
    ):
        """Test collecting metrics from multiple devices."""
        mock_post.return_value.json.return_value = {"access_token": mock_access_token}
        mock_get.return_value.json.return_value = {"data": mock_device_data}

        device_ids = ["device1", "device2", "device3"]
        collector = CloudCollector("client_id", "client_secret", device_ids)
        metrics = list(collector.collect())

        assert len(metrics) == 1
        assert mock_get.call_count == len(device_ids)
