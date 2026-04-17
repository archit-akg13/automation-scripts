"""Retry helper — decorator and callable for retrying flaky operations.

Provides a retry decorator with exponential backoff and full jitter,
plus a retry_call function for ad-hoc use. Useful for wrapping network
requests, database connections, or any operation that can fail transiently.

Usage:
    from retry_helper import retry, retry_call

        @retry(max_attempts=5, base_delay=0.5, max_delay=10.0)
            def fetch(url):
                    return requests.get(url, timeout=5).json()

                        # Or call directly without decorating:
                            result = retry_call(fetch, "https://api.example.com", max_attempts=3)
                            """

from __future__ import annotations

import logging
import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)

RetryableExceptions = Tuple[Type[BaseException], ...]
OnRetryCallback = Callable[[BaseException, int, float], None]


def _compute_delay(attempt: int, base_delay: float, max_delay: float, jitter: bool) -> float:
      """Compute backoff delay for a given attempt (1-indexed)."""
      raw = base_delay * (2 ** (attempt - 1))
      capped = min(raw, max_delay)
      if jitter:
                return random.uniform(0, capped)
            return capped


def retry(
      max_attempts: int = 3,
      base_delay: float = 0.5,
      max_delay: float = 30.0,
      exceptions: RetryableExceptions = (Exception,),
      jitter: bool = True,
      on_retry: Optional[OnRetryCallback] = None,
) -> Callable:
      """Decorator: retry a function with exponential backoff and full jitter."""
    if max_attempts < 1:
              raise ValueError("max_attempts must be >= 1")

    def decorator(func: Callable) -> Callable:
              @wraps(func)
              def wrapper(*args: Any, **kwargs: Any) -> Any:
                  last_exc: Optional[BaseException] = None
            for attempt in range(1, max_attempts + 1):
                              try:
                                                    return func(*args, **kwargs)
except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                                              logger.warning(
                                                                            "retry: %s exhausted %d attempts: %s",
                                                                            func.__name__, max_attempts, exc,
                                              )
                                              raise
                                          delay = _compute_delay(attempt, base_delay, max_delay, jitter)
                    if on_retry is not None:
                                              try:
                                                                            on_retry(exc, attempt, delay)
except Exception:
                            logger.exception("retry: on_retry callback failed")
                    logger.info(
                                              "retry: %s attempt %d/%d failed (%s); sleeping %.2fs",
                                              func.__name__, attempt, max_attempts, exc, delay,
                    )
                    time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator


def retry_call(
      func: Callable,
      *args: Any,
            max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    exceptions: RetryableExceptions = (Exception,),
    jitter: bool = True,
    on_retry: Optional[OnRetryCallback] = None,
    **kwargs: Any,
) -> Any:
    """Call func(*args, **kwargs) with retry semantics."""
    decorated = retry(
              max_attempts=max_attempts,
              base_delay=base_delay,
              max_delay=max_delay,
              exceptions=exceptions,
              jitter=jitter,
              on_retry=on_retry,
    )(func)
    return decorated(*args, **kwargs)


if __name__ == "__main__":
      logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    counter = {"n": 0}

    @retry(max_attempts=5, base_delay=0.1, max_delay=1.0)
    def flaky() -> str:
              counter["n"] += 1
        if counter["n"] < 3:
                      raise ConnectionError(f"boom (attempt {counter['n']})")
                  return "ok"

    print("Result:", flaky())
    print("Attempts taken:", counter["n"])
