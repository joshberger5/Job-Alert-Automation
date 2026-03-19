"""
Tests for ResumeProfileBuilder behavioral contracts.

Covers:
  SCORE-01: minimum_salary and reason tags loaded from candidate_profile.yaml
  SCORE-03: tertiary_skills taxonomy filtering (occurrence threshold + taxonomy lookup)
"""

import os
from typing import Any
from unittest.mock import patch

from application.resume_profile_builder import ResumeProfileBuilder

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_RESUME: str = """
Technical Skills
Languages: Java, Python
Frameworks: Spring, Hibernate

Experience
January 2022 – Present
Software Engineer at Acme Corp
"""


def _make_config(**overrides: Any) -> dict[str, Any]:
    """Return a minimal _ProfileConfig dict with optional overrides."""
    base: dict[str, Any] = {
        "preferred_locations": ["Jacksonville, FL"],
        "remote_allowed": True,
        "open_to_contract": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# SCORE-01: minimum_salary loaded from YAML
# ---------------------------------------------------------------------------


def test_minimum_salary_loaded_from_yaml() -> None:
    """Profile.minimum_salary should equal the value in candidate_profile.yaml."""
    config: dict[str, Any] = _make_config(minimum_salary=90000)
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    with patch("application.resume_profile_builder.ResumeProfileBuilder._load_config", return_value=config):
        profile = builder.build(_MINIMAL_RESUME)
    assert profile.minimum_salary == 90000


def test_minimum_salary_defaults_to_zero() -> None:
    """Profile.minimum_salary should default to 0 when key is absent from YAML."""
    config: dict[str, Any] = _make_config()  # no minimum_salary key
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    with patch("application.resume_profile_builder.ResumeProfileBuilder._load_config", return_value=config):
        profile = builder.build(_MINIMAL_RESUME)
    assert profile.minimum_salary == 0


def test_reason_tags_loaded_from_yaml() -> None:
    """feedback_thumbs_down_reasons and feedback_thumbs_up_reasons should be loaded from YAML."""
    config: dict[str, Any] = _make_config(
        feedback_thumbs_down_reasons=["Bad company"],
        feedback_thumbs_up_reasons=["Great pay"],
    )
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    with patch("application.resume_profile_builder.ResumeProfileBuilder._load_config", return_value=config):
        profile = builder.build(_MINIMAL_RESUME)
    assert profile.feedback_thumbs_down_reasons == ["Bad company"]
    assert profile.feedback_thumbs_up_reasons == ["Great pay"]


# ---------------------------------------------------------------------------
# SCORE-03: tertiary_skills taxonomy filtering
# ---------------------------------------------------------------------------

_RESUME_WITH_DOCKER_TWICE: str = """
Technical Skills
Languages: Java, Python

Experience
January 2022 – Present
Software Engineer at Acme Corp
Used Docker to containerize services. Docker improved deployment speed.

Projects
Sample Project
"""

_RESUME_WITH_ONE_OCCURRENCE: str = """
Technical Skills
Languages: Java, Python

Experience
January 2022 – Present
Software Engineer at Acme Corp
Used Widgetlang to process data.

Projects
Sample Project
"""

_RESUME_WITH_WIDGETLANG_TWICE: str = """
Technical Skills
Languages: Java, Python

Experience
January 2022 – Present
Software Engineer at Acme Corp
Used Widgetlang to process data. Widgetlang improved throughput.

Projects
Sample Project
"""


def test_single_occurrence_token_excluded() -> None:
    """A capitalized token appearing only once in Experience must NOT be in tertiary_skills."""
    config: dict[str, Any] = _make_config()
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    taxonomy: frozenset[str] = frozenset()  # Widgetlang not in taxonomy
    with patch("application.resume_profile_builder.ResumeProfileBuilder._load_config", return_value=config), \
         patch("application.resume_profile_builder._load_taxonomy", return_value=taxonomy):
        profile = builder.build(_RESUME_WITH_ONE_OCCURRENCE)
    assert "widgetlang" not in profile.tertiary_skills


def test_taxonomy_token_included() -> None:
    """A token in the taxonomy appearing twice should be in tertiary_skills."""
    config: dict[str, Any] = _make_config()
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    taxonomy: frozenset[str] = frozenset({"docker"})
    with patch("application.resume_profile_builder.ResumeProfileBuilder._load_config", return_value=config), \
         patch("application.resume_profile_builder._load_taxonomy", return_value=taxonomy):
        profile = builder.build(_RESUME_WITH_DOCKER_TWICE)
    assert "docker" in profile.tertiary_skills


def test_bare_numbers_excluded_from_tertiary_skills() -> None:
    """Bare numbers like '30', '2024', '50' must not become tertiary tokens even if repeated."""
    resume: str = """
Technical Skills
Languages: Java, Python

Experience
January 2022 – Present
Software Engineer at Acme Corp
Automated metadata for 30,000 fields, saving 30 minutes per screen.
Worked with a team of 50 engineers. Delivered in 2024. Also 2024 award.

Projects
Sample Project
"""
    config: dict[str, Any] = _make_config()
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    taxonomy: frozenset[str] = frozenset()
    env_without_gemini: dict[str, str] = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    with patch("application.resume_profile_builder.ResumeProfileBuilder._load_config", return_value=config), \
         patch("application.resume_profile_builder._load_taxonomy", return_value=taxonomy), \
         patch.dict(os.environ, env_without_gemini, clear=True):
        profile = builder.build(resume)
    assert "30" not in profile.tertiary_skills
    assert "50" not in profile.tertiary_skills
    assert "2024" not in profile.tertiary_skills


def test_alphanumeric_tech_tokens_still_included() -> None:
    """Tokens like 'ES6', 'Python3' (letter+digit) must still be included as tertiary."""
    resume: str = """
Technical Skills
Languages: Java

Experience
January 2022 – Present
Software Engineer at Acme Corp
Wrote ES6 modules and ES6 components. Used Python3 scripts and Python3 tooling.

Projects
Sample Project
"""
    config: dict[str, Any] = _make_config()
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    taxonomy: frozenset[str] = frozenset({"es6", "python3"})
    with patch("application.resume_profile_builder.ResumeProfileBuilder._load_config", return_value=config), \
         patch("application.resume_profile_builder._load_taxonomy", return_value=taxonomy):
        profile = builder.build(resume)
    assert "es6" in profile.tertiary_skills
    assert "python3" in profile.tertiary_skills


def test_unknown_token_kept_without_gemini_key() -> None:
    """Unknown token (not in taxonomy) appearing twice is kept when GEMINI_API_KEY is absent."""
    config: dict[str, Any] = _make_config()
    builder: ResumeProfileBuilder = ResumeProfileBuilder()
    taxonomy: frozenset[str] = frozenset()  # Widgetlang not in taxonomy
    env_without_gemini: dict[str, str] = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    with patch("application.resume_profile_builder.ResumeProfileBuilder._load_config", return_value=config), \
         patch("application.resume_profile_builder._load_taxonomy", return_value=taxonomy), \
         patch.dict(os.environ, env_without_gemini, clear=True):
        profile = builder.build(_RESUME_WITH_WIDGETLANG_TWICE)
    assert "widgetlang" in profile.tertiary_skills
