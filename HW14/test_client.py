import time
import pytest
from unittest.mock import patch, Mock
from client import get_data, get_data_with_circuit_breaker, ExponentialBackoff, CircuitBreaker


@pytest.fixture
def strategy():
    return ExponentialBackoff()


@pytest.fixture
def circuit_breaker():
    return CircuitBreaker()


@patch("client.requests.get")
def test_successful_request(mock_get, strategy):
    # Arrange
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "OK"

    # Act
    result = get_data("http://example.com", strategy)

    # Assert
    assert result == "OK"


@patch("client.requests.get")
def test_retry_on_500(mock_get, strategy):
    # Arrange
    mock_get.side_effect = [
        Mock(status_code=500),
        Mock(status_code=500),
        Mock(status_code=200, text="Success")
    ]

    # Act
    result = get_data("http://example.com", strategy)

    # Assert
    assert result == "Success"


@patch("client.requests.get")
def test_failure_after_retries(mock_get, strategy):
    # Arrange
    mock_get.side_effect = [
        Mock(status_code=500),
        Mock(status_code=502),
        Mock(status_code=503)
    ]

    # Act & Assert
    with pytest.raises(Exception) as excinfo:
        get_data("http://example.com", strategy)
    assert "API не ответило корректно" in str(excinfo.value)


@patch("client.requests.get")
def test_circuit_breaker_open(mock_get, strategy, circuit_breaker):
    # Arrange
    mock_get.side_effect = [Mock(status_code=500)] * 3

    # Act & Assert
    with pytest.raises(Exception):
        get_data_with_circuit_breaker("http://example.com", strategy, circuit_breaker)

    with pytest.raises(Exception) as excinfo:
        get_data_with_circuit_breaker("http://example.com", strategy, circuit_breaker)
    assert "Circuit Breaker is OPEN" in str(excinfo.value)


@patch("client.requests.get")
def test_circuit_breaker_half_open(mock_get, strategy, circuit_breaker):
    # Arrange
    mock_get.side_effect = [Mock(status_code=500)] * 3 + [Mock(status_code=200, text="Recovered")]

    # Act & Assert
    with pytest.raises(Exception):
        get_data_with_circuit_breaker("http://example.com", strategy, circuit_breaker)

    time.sleep(circuit_breaker.reset_timeout)
    result = get_data_with_circuit_breaker("http://example.com", strategy, circuit_breaker)

    assert result == "Recovered"