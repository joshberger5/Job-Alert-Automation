from application.fetcher_result import FetcherFailure


def test_fetcher_failure_fields() -> None:
    f: FetcherFailure = {"company": "Acme", "error": "connection refused", "attempts": 2}
    assert f["company"] == "Acme"
    assert f["error"] == "connection refused"
    assert f["attempts"] == 2


def test_fetcher_failure_timeout() -> None:
    f: FetcherFailure = {"company": "Acme", "error": "TIMEOUT", "attempts": 1}
    assert f["error"] == "TIMEOUT"
    assert f["attempts"] == 1
