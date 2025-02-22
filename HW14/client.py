import requests
import time
import logging
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RetryStrategy(ABC):
    @abstractmethod
    def get_delay(self, attempt: int) -> int:
        pass


class ExponentialBackoff(RetryStrategy):
    def get_delay(self, attempt: int) -> int:
        return 2 ** (attempt - 1) if attempt > 0 else 0


def get_data(url: str, strategy: RetryStrategy) -> str:
    retries = 3

    for attempt in range(retries):
        if attempt > 0:
            delay = strategy.get_delay(attempt)
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)

        try:
            response = requests.get(url)
            if response.status_code == 200:
                logger.info("Request successful")
                return response.text
            elif response.status_code in {500, 502, 503, 504}:
                logger.warning(f"Server error {response.status_code}, retrying...")
                continue
            else:
                response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            if attempt == retries - 1:
                raise e

    raise Exception("API не ответило корректно после 3 попыток")


class CircuitBreaker:
    def __init__(self, failure_threshold=3, reset_timeout=10):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None

    def allow_request(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.reset_timeout:
                logger.info("Circuit Breaker moving to HALF-OPEN state")
                self.state = "HALF-OPEN"
                return True
            logger.warning("Circuit Breaker is OPEN. Requests are blocked.")
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
        logger.info("Circuit Breaker reset to CLOSED state")

    def record_failure(self):
        self.failure_count += 1
        logger.warning(f"Failure recorded. Count: {self.failure_count}")
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.last_failure_time = time.time()
            logger.error("Circuit Breaker is now OPEN")


def get_data_with_circuit_breaker(url: str, strategy: RetryStrategy, circuit_breaker: CircuitBreaker) -> str:
    if not circuit_breaker.allow_request():
        raise Exception("Circuit Breaker is OPEN. Requests are blocked.")

    retries = 3
    for attempt in range(retries):
        if attempt > 0:
            delay = strategy.get_delay(attempt)
            logger.info(f"Retrying in {delay} seconds...")
            time.sleep(delay)

        try:
            response = requests.get(url)
            if response.status_code == 200:
                circuit_breaker.record_success()
                logger.info("Request successful")
                return response.text
            elif response.status_code in {500, 502, 503, 504}:
                circuit_breaker.record_failure()
                logger.warning(f"Server error {response.status_code}, retrying...")
                continue
            else:
                response.raise_for_status()
        except requests.RequestException as e:
            circuit_breaker.record_failure()
            logger.error(f"Request failed: {e}")
            if attempt == retries - 1:
                raise Exception("API не ответило корректно после 3 попыток")

    raise Exception("API не ответило корректно после 3 попыток")
