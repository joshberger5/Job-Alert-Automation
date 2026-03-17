from datetime import datetime

from application.job_record import JobRecord
from infrastructure.email_notifier import build_email_html as _build_html, _section


def _html(run_log: str = "") -> str:
    return _build_html(
        jobs=[],
        run_at=datetime(2026, 3, 15, 10, 0),
        duration_s=12.5,
        total_fetched=100,
        run_log=run_log,
    )


# ---------------------------------------------------------------------------
# Run Log section presence
# ---------------------------------------------------------------------------


def test_run_log_section_heading_present() -> None:
    html: str = _html("some output")
    assert "Run Log" in html


def test_run_log_content_appears_in_html() -> None:
    html: str = _html("fetched 42 jobs")
    assert "fetched 42 jobs" in html


def test_run_log_section_present_when_empty() -> None:
    """Empty run_log should still render the section without error."""
    html: str = _html("")
    assert "Run Log" in html


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------


def test_run_log_less_than_is_escaped() -> None:
    html: str = _html("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_run_log_ampersand_is_escaped() -> None:
    html: str = _html("a & b")
    assert "a & b" not in html
    assert "a &amp; b" in html


def test_run_log_greater_than_is_escaped() -> None:
    html: str = _html("score > 7")
    assert "score > 7" not in html
    assert "score &gt; 7" in html


# ---------------------------------------------------------------------------
# Default run_log omitted
# ---------------------------------------------------------------------------


def test_run_log_defaults_to_empty_string() -> None:
    """Calling _build_html without run_log should not raise."""
    html: str = _build_html(
        jobs=[],
        run_at=datetime(2026, 3, 15, 10, 0),
        duration_s=5.0,
        total_fetched=0,
    )
    assert "Run Log" in html


# ---------------------------------------------------------------------------
# Score ordering
# ---------------------------------------------------------------------------


def _make_job(title: str, score: int) -> JobRecord:
    job: JobRecord = JobRecord(
        id="id",
        title=title,
        company="Co",
        location="",
        score=score,
        result="qualified",
        score_breakdown={},
        feedback_multiplier=1.0,
    )
    return job


def test_qualified_jobs_ordered_by_score_descending() -> None:
    jobs: list[JobRecord] = [
        _make_job("Low", 7),
        _make_job("High", 20),
        _make_job("Mid", 12),
    ]
    html: str = _build_html(
        jobs=jobs,
        run_at=datetime(2026, 3, 15, 10, 0),
        duration_s=5.0,
        total_fetched=50,
    )
    high_pos: int = html.index("High")
    mid_pos: int = html.index("Mid")
    low_pos: int = html.index("Low")
    assert high_pos < mid_pos < low_pos


def test_section_jobs_ordered_by_score_descending() -> None:
    jobs: list[JobRecord] = [
        _make_job("Low", 3),
        _make_job("High", 15),
        _make_job("Mid", 9),
    ]
    html: str = _section(
        comment="TEST",
        heading="Test Section",
        subtext="desc",
        jobs=jobs,
    )
    high_pos: int = html.index("High")
    mid_pos: int = html.index("Mid")
    low_pos: int = html.index("Low")
    assert high_pos < mid_pos < low_pos


def test_score_ordering_does_not_mutate_input_list() -> None:
    jobs: list[JobRecord] = [
        _make_job("Low", 7),
        _make_job("High", 20),
    ]
    original_order: list[str] = [j["title"] for j in jobs]
    _build_html(
        jobs=jobs,
        run_at=datetime(2026, 3, 15, 10, 0),
        duration_s=5.0,
        total_fetched=10,
    )
    assert [j["title"] for j in jobs] == original_order


# ---------------------------------------------------------------------------
# FEED-01: Vote links in job card
# ---------------------------------------------------------------------------


def test_vote_links_present_in_job_card() -> None:
    """When FEEDBACK_PAT is set, job card HTML contains vote links with correct params."""
    import os
    from unittest.mock import patch as mock_patch
    from infrastructure.email_notifier import _job_card
    job: JobRecord = _make_job("Java Developer", 12)
    job["id"] = "job-abc-123"
    job["company"] = "ACME Corp"
    with mock_patch.dict(os.environ, {"FEEDBACK_PAT": "test_pat_xyz"}):
        card_html: str = _job_card(job)
    assert "feedback.html" in card_html
    assert "job-abc-123" in card_html
    assert "%2B1" in card_html or "+1" in card_html  # URL-encoded or raw +1
    assert "-1" in card_html


def test_vote_links_omitted_when_no_pat() -> None:
    """When FEEDBACK_PAT is absent, job card HTML does NOT contain vote links."""
    import os
    from unittest.mock import patch as mock_patch
    from infrastructure.email_notifier import _job_card
    job: JobRecord = _make_job("Java Developer", 12)
    job["id"] = "job-abc-123"
    with mock_patch.dict(os.environ, {}, clear=True):
        # Ensure FEEDBACK_PAT is absent
        os.environ.pop("FEEDBACK_PAT", None)
        card_html: str = _job_card(job)
    assert "feedback.html" not in card_html


def test_vote_link_relevant_has_explicit_blue_color() -> None:
    """'Relevant' link must carry color:#3b82f6 — no explicit color renders purple in email clients."""
    import os
    from unittest.mock import patch as mock_patch
    from infrastructure.email_notifier import _job_card
    job: JobRecord = _make_job("Java Dev", 10)
    job["id"] = "job-xyz"
    job["company"] = "Corp"
    with mock_patch.dict(os.environ, {"FEEDBACK_PAT": "token"}):
        card_html: str = _job_card(job)
    assert "color:#3b82f6" in card_html


def test_vote_link_icons_use_img_not_svg() -> None:
    """Vote icons must use <img> elements not inline <svg> — email clients strip inline SVG."""
    import os
    from unittest.mock import patch as mock_patch
    from infrastructure.email_notifier import _job_card
    job: JobRecord = _make_job("Java Dev", 10)
    job["id"] = "job-xyz"
    job["company"] = "Corp"
    with mock_patch.dict(os.environ, {"FEEDBACK_PAT": "token"}):
        card_html: str = _job_card(job)
    assert "<img" in card_html
    assert "<svg" not in card_html


def test_vote_link_url_structure() -> None:
    """Vote link contains job_id, vote, title, company as query params; token after #."""
    import os
    import urllib.parse
    from unittest.mock import patch as mock_patch
    from infrastructure.email_notifier import _job_card
    job: JobRecord = _make_job("Java Dev", 10)
    job["id"] = "job-xyz"
    job["company"] = "Big Corp"
    with mock_patch.dict(os.environ, {"FEEDBACK_PAT": "mytoken123"}):
        card_html: str = _job_card(job)
    # Token must appear after # (in fragment), not as query param
    assert "#mytoken123" in card_html
    assert "?mytoken123" not in card_html
    assert "job_id=" in card_html
    assert "vote=" in card_html
