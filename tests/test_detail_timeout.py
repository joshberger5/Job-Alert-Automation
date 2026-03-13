"""Tests that _DETAIL_TIMEOUT == 12 in all three detail-page fetchers (red until Plan 02-06)."""
import infrastructure.job_fetchers.workday_fetcher as wf
import infrastructure.job_fetchers.icims_fetcher as icf
import infrastructure.job_fetchers.adzuna_similar_fetcher as asf


def test_workday_detail_timeout() -> None:
    assert wf._DETAIL_TIMEOUT == 12


def test_icims_detail_timeout() -> None:
    assert icf._DETAIL_TIMEOUT == 12


def test_adzuna_similar_detail_timeout() -> None:
    assert asf._DETAIL_TIMEOUT == 12
