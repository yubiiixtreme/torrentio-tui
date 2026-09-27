"""Generic exponential-backoff retry for flaky I/O (network calls, not
subprocess spawns). Kept provider-agnostic -- callers pass the operation
and which exceptions count as retryable.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def call_with_backoff(
    func: Callable[[], T],
    *,
    retryable: tuple[type[Exception], ...] | type[Exception],
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    jitter: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call `func()`, retrying up to `attempts` times on a `retryable`
    exception with exponential backoff (`base_delay * 2**n`, capped at
    `max_delay`) plus up to `jitter` fraction of random jitter so
    simultaneous retries don't all land on the same instant. Re-raises
    the last exception once attempts are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return func()
        except retryable as exc:  # noqa: PERF203 -- retry loop, not a hot path
            last_exc = exc
            if attempt == attempts - 1:
                break
            delay = min(base_delay * (2**attempt), max_delay)
            delay += delay * jitter * random.random()
            sleep(delay)
    assert last_exc is not None
    raise last_exc
