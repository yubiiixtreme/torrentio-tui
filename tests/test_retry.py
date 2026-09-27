from __future__ import annotations

import pytest

from torrentio_tui.retry import call_with_backoff


def test_retries_until_success():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return "ok"

    result = call_with_backoff(flaky, retryable=ConnectionError, attempts=5, sleep=lambda _: None)
    assert result == "ok"
    assert calls["n"] == 3


def test_raises_after_exhausting_attempts():
    def always_fails():
        raise ConnectionError("boom")

    with pytest.raises(ConnectionError):
        call_with_backoff(always_fails, retryable=ConnectionError, attempts=3, sleep=lambda _: None)


def test_non_retryable_exception_propagates_immediately():
    calls = {"n": 0}

    def raises_value_error():
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError, match="not retryable"):
        call_with_backoff(
            raises_value_error, retryable=ConnectionError, attempts=5, sleep=lambda _: None
        )
    assert calls["n"] == 1


def test_backoff_delay_grows_and_is_capped():
    delays = []

    def always_fails():
        raise ConnectionError("boom")

    with pytest.raises(ConnectionError):
        call_with_backoff(
            always_fails,
            retryable=ConnectionError,
            attempts=4,
            base_delay=1.0,
            max_delay=3.0,
            jitter=0.0,
            sleep=delays.append,
        )
    assert delays == [1.0, 2.0, 3.0]
