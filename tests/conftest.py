import pytest


@pytest.fixture
def mock_access_token():
    """Mock access token for API authentication."""
    return "mock_access_token_12345"


@pytest.fixture
def mock_device_id():
    """Mock device ID."""
    return "1234567890"


@pytest.fixture
def mock_client_credentials():
    """Mock client credentials."""
    return {
        "client_id": "test_client_id",
        "client_secret": "test_client_secret",
    }


@pytest.fixture
def mock_device_data():
    """Mock device data returned from Airthings API."""
    return {
        "battery": 95,
        "co2": 450,
        "humidity": 45.5,
        "pm1": 2.1,
        "pm25": 3.5,
        "pressure": 1013.25,
        "radonShortTermAvg": 25.0,
        "temp": 22.5,
        "voc": 150,
    }
