import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, TypedDict, cast

import requests
import yaml

from domain.candidate_profile import CandidateProfile


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_PATH: Path = Path(__file__).parent.parent / "candidate_profile.yaml"
_TAXONOMY_PATH: Path = Path(__file__).parent.parent / "infrastructure" / "tech_taxonomy.yaml"
_CACHE_PATH: Path = Path(__file__).parent.parent / "infrastructure" / "tertiary_cache.json"
_RESUME_PATH: Path = Path(__file__).parent.parent / "resume.tex"

_GEMINI_URL: str = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-2.0-flash-lite:generateContent"
)


class _ProfileConfig(TypedDict, total=False):
    preferred_locations: list[str]
    remote_allowed: bool
    open_to_contract: bool
    minimum_salary: int
    feedback_thumbs_down_reasons: list[str]
    feedback_thumbs_up_reasons: list[str]


# ---------------------------------------------------------------------------
# Section regexes
# ---------------------------------------------------------------------------

_ALL_SECTIONS: str = (
    r'(?:Work\s+)?(?:Experience|Education|Projects?|Summary'
    r'|Certifications?|Technical\s+Skills?)'
)

_SKILLS_SECTION: re.Pattern[str] = re.compile(
    rf'Technical Skills?\s*\n(.*?)(?=\n{_ALL_SECTIONS}\b|\Z)',
    re.DOTALL | re.IGNORECASE,
)

_EXPERIENCE_SECTION: re.Pattern[str] = re.compile(
    rf'(?:Work\s+)?Experience\s*\n(.*?)(?=\n{_ALL_SECTIONS}\b|\Z)',
    re.DOTALL | re.IGNORECASE,
)

_PROJECTS_SECTION: re.Pattern[str] = re.compile(
    rf'Projects?\s*\n(.*?)(?=\n{_ALL_SECTIONS}\b|\Z)',
    re.DOTALL | re.IGNORECASE,
)

_CATEGORY_LINE: re.Pattern[str] = re.compile(r'^[^:\n]+:\s*(.+)$', re.MULTILINE)

# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_MONTHS: dict[str, int] = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}

_MONTH_PAT: str = (
    r'(?:January|February|March|April|May|June|July'
    r'|August|September|October|November|December)'
)

# Matches all three formats:
#   "Month Year – Month Year"  (different years)
#   "Month Year – Present"
#   "Month – Month Year"       (same year; start year absent)
_DATE_RANGE: re.Pattern[str] = re.compile(
    rf'({_MONTH_PAT})(?:\s+(\d{{4}}))?\s*[–\-]+\s*({_MONTH_PAT}|Present)(?:\s+(\d{{4}}))?',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Token extraction stop-words
# ---------------------------------------------------------------------------

_STOP_WORDS: frozenset[str] = frozenset({
    # Articles / prepositions / conjunctions
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
    'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    'would', 'could', 'should', 'may', 'might', 'shall', 'can', 'need',
    'i', 'we', 'you', 'he', 'she', 'it', 'they', 'my', 'our', 'your',
    'his', 'her', 'its', 'their', 'this', 'that', 'these', 'those',
    'which', 'who', 'what', 'where', 'when', 'how', 'all', 'each',
    'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'not', 'only', 'same', 'than', 'too', 'very', 'just', 'also',
    'across', 'after', 'before', 'between', 'into', 'through', 'during',
    'including', 'while', 'using', 'within', 'about', 'against', 'among',
    'without', 'under', 'over', 'then', 'so', 'if', 'up', 'new',
    # Resume action verbs
    'developed', 'implemented', 'built', 'created', 'designed', 'led',
    'managed', 'improved', 'increased', 'reduced', 'delivered', 'deployed',
    'integrated', 'optimized', 'maintained', 'collaborated', 'supported',
    'contributed', 'utilized', 'leveraged', 'ensured', 'provided',
    'established', 'streamlined', 'automated', 'migrated', 'refactored',
    'debugged', 'tested', 'monitored', 'configured', 'architected',
    'spearheaded', 'coordinated', 'facilitated', 'participated',
    # Common tech-adjacent nouns that aren't skill keywords
    'software', 'development', 'engineer', 'engineering', 'system', 'systems',
    'platform', 'service', 'services', 'solution', 'solutions', 'feature',
    'features', 'functionality', 'code', 'codebase', 'test', 'tests',
    'testing', 'performance', 'experience', 'project', 'projects',
    'application', 'applications', 'pipeline', 'workflow', 'process',
    'environment', 'production', 'team', 'teams', 'member', 'stakeholder',
    'stakeholders', 'client', 'clients', 'customer', 'customers', 'business',
    'user', 'users', 'scalable', 'reliable', 'data', 'based', 'work',
    'worked', 'working', 'multiple', 'large', 'small', 'high', 'low',
    'internal', 'existing', 'various', 'different', 'key', 'main', 'core',
    'full', 'well', 'best', 'practices', 'strong', 'knowledge',
    'understanding', 'ability', 'skills', 'responsible',
    # Months (appear in date ranges inside experience section)
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    # Misc
    'present', 'current', 'etc', 'via', 'remote', 'hybrid',
    'florida', 'jacksonville',
    # Generic tech terms already covered by secondary skills (e.g. 'rest apis')
    'api', 'rest',
    # Frontend/tooling tokens not relevant to backend scoring
    'html', 'github',
    # Generic action words that appear frequently but aren't technical skills
    'actions',
})


# ---------------------------------------------------------------------------
# Taxonomy and cache helpers
# ---------------------------------------------------------------------------

def _load_taxonomy() -> frozenset[str]:
    """Load the tech token taxonomy from tech_taxonomy.yaml.

    Returns a frozenset of lowercase tokens. Returns frozenset() on any error
    (fail-open: empty taxonomy means all tokens go through the keep/Gemini path).
    """
    try:
        with open(_TAXONOMY_PATH, 'r') as f:
            data: dict[str, Any] = yaml.safe_load(f)
        return frozenset(data["tokens"])
    except Exception:
        return frozenset()


def _get_resume_hash() -> str | None:
    """Return MD5 hex digest of resume.tex content, or None on error."""
    try:
        content: bytes = _RESUME_PATH.read_bytes()
        return hashlib.md5(content).hexdigest()
    except Exception:
        return None


def _load_classification_cache(resume_hash: str | None) -> dict[str, bool]:
    """Load Gemini classification cache from disk.

    Returns {} if the cache file does not exist, resume_hash is None, or the
    stored hash does not match the current resume hash (cache invalidated).
    """
    if resume_hash is None:
        return {}
    try:
        if not _CACHE_PATH.exists():
            return {}
        with open(_CACHE_PATH, 'r') as f:
            raw: dict[str, Any] = json.load(f)
        if raw.get("resume_hash") != resume_hash:
            return {}
        classifications: dict[str, bool] = raw.get("classifications", {})
        return classifications
    except Exception:
        return {}


def _save_classification_cache(
    resume_hash: str | None,
    classifications: dict[str, bool],
) -> None:
    """Persist classification cache to disk. Silently ignores write errors."""
    try:
        payload: dict[str, Any] = {
            "resume_hash": resume_hash or "",
            "classifications": classifications,
        }
        with open(_CACHE_PATH, 'w') as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass


def _gemini_classify_batch(tokens: list[str]) -> dict[str, bool]:
    """Call Gemini to classify tokens as tech (True) or non-tech (False).

    If GEMINI_API_KEY is not set, returns all True (keep all).
    Fails open — any exception returns all True so no tokens are silently dropped.
    """
    api_key: str | None = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {t: True for t in tokens}

    prompt: str = (
        "Classify each of the following tokens as a technical skill (true) "
        "or not a technical skill (false). "
        "A technical skill is a programming language, framework, library, "
        "tool, platform, protocol, or technology used in software development. "
        f"Tokens: {tokens}. "
        'Return ONLY a JSON object mapping each token to true or false, '
        'e.g. {"docker": true, "meeting": false}. '
        "No explanation, no markdown."
    )

    try:
        response = requests.post(
            _GEMINI_URL,
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0},
            },
            timeout=20,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        raw_text: str = data["candidates"][0]["content"]["parts"][0]["text"]
        # Strip markdown fences if present
        raw_text = re.sub(r"```[a-z]*\n?", "", raw_text).strip()
        result: dict[str, bool] = json.loads(raw_text)
        # Ensure all requested tokens are present; default missing ones to True
        return {t: result.get(t, True) for t in tokens}
    except Exception:
        return {t: True for t in tokens}


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class ResumeProfileBuilder:

    def build(self, resume_text: str) -> CandidateProfile:
        config: _ProfileConfig = self._load_config()

        primary_skills, other_skills = self._extract_skills(resume_text)
        core_skills: dict[str, int] = {s.lower(): 4 for s in primary_skills}
        secondary_skills: dict[str, int] = {s.lower(): 2 for s in other_skills}

        extra_tokens: list[str] = self._extract_extra_tokens(
            resume_text, core_skills, secondary_skills
        )
        tertiary_skills: dict[str, int] = {s: 1 for s in extra_tokens}

        experience_years: int = self._calculate_experience_years(resume_text)

        return CandidateProfile(
            preferred_locations=config['preferred_locations'],
            remote_allowed=config['remote_allowed'],
            ideal_max_experience_years=experience_years,
            core_skills=core_skills,
            secondary_skills=secondary_skills,
            tertiary_skills=tertiary_skills,
            open_to_contract=config.get('open_to_contract', False),
            minimum_salary=config.get('minimum_salary', 0),
            feedback_thumbs_down_reasons=config.get('feedback_thumbs_down_reasons', []),
            feedback_thumbs_up_reasons=config.get('feedback_thumbs_up_reasons', []),
        )

    def _load_config(self) -> _ProfileConfig:
        with open(_CONFIG_PATH, 'r') as f:
            return cast(_ProfileConfig, yaml.safe_load(f))

    def _extract_skills(self, resume_text: str) -> tuple[list[str], list[str]]:
        section_match: re.Match[str] | None = _SKILLS_SECTION.search(resume_text)
        if not section_match:
            return [], []

        categories: list[list[str]] = []
        for line_match in _CATEGORY_LINE.finditer(section_match.group(1)):
            items: list[str] = [s.strip() for s in line_match.group(1).split(',')]
            categories.append([s for s in items if s])

        if not categories:
            return [], []

        primary: list[str] = categories[0]
        secondary: list[str] = [skill for cat in categories[1:] for skill in cat]
        return primary, secondary

    def _extract_extra_tokens(
        self,
        resume_text: str,
        core_skills: dict[str, int],
        secondary_skills: dict[str, int],
    ) -> list[str]:
        already_known: set[str] = set(core_skills.keys()) | set(secondary_skills.keys())

        extra_text_parts: list[str] = []
        for section_re in (_EXPERIENCE_SECTION, _PROJECTS_SECTION):
            m: re.Match[str] | None = section_re.search(resume_text)
            if m:
                extra_text_parts.append(m.group(1))

        if not extra_text_parts:
            return []

        combined: str = '\n'.join(extra_text_parts)
        token_counts: Counter[str] = Counter()

        for raw in re.findall(r'[\w+#.-]+', combined):
            lower: str = raw.lower()
            if lower in already_known or lower in _STOP_WORDS or len(raw) < 2:
                continue
            # Keep tokens that look like tech: special chars, digits, or capitalized
            if (
                re.search(r'[+#.]', raw)                          # e.g. Node.js, C++, C#
                or (re.search(r'\d', raw) and re.search(r'[a-zA-Z]', raw))  # e.g. ES6, Python3 (not bare numbers)
                or raw[0].isupper()                               # e.g. Docker, PostgreSQL
            ):
                token_counts[lower] += 1

        # Frequency filter: discard single-occurrence tokens (noise)
        candidates: list[str] = [t for t, c in token_counts.items() if c >= 2]

        # Taxonomy gate
        taxonomy: frozenset[str] = _load_taxonomy()
        resume_hash: str | None = _get_resume_hash()
        cache: dict[str, bool] = _load_classification_cache(resume_hash)

        known_in_taxonomy: list[str] = [t for t in candidates if t in taxonomy]
        unknown: list[str] = [t for t in candidates if t not in taxonomy]

        # Classify unknowns via Gemini (or fail-open if no API key)
        to_classify: list[str] = [t for t in unknown if t not in cache]
        if to_classify:
            new_classifications: dict[str, bool] = _gemini_classify_batch(to_classify)
            cache.update(new_classifications)
            _save_classification_cache(resume_hash, cache)

        keep_unknown: list[str] = [t for t in unknown if cache.get(t, True)]
        result: list[str] = sorted(set(known_in_taxonomy) | set(keep_unknown))
        return result

    def _calculate_experience_years(self, resume_text: str) -> int:
        experience_match: re.Match[str] | None = _EXPERIENCE_SECTION.search(resume_text)
        if not experience_match:
            return 0

        total_months: int = 0
        today: date = date.today()

        for m in _DATE_RANGE.finditer(experience_match.group(1)):
            start_month_name: str = m.group(1)
            start_year_raw: str | None = m.group(2)
            end_str: str = m.group(3)
            end_year_raw: str | None = m.group(4)

            end_is_present: bool = end_str.lower() == 'present'

            if end_is_present:
                end_year: int = today.year
                end_month: int = today.month
            elif end_year_raw is not None:
                end_year = int(end_year_raw)
                end_month = _MONTHS[end_str.lower()]
            else:
                continue  # malformed date range; skip

            # If start year is absent it's a same-year range (e.g. "May – August 2024")
            start_year: int = int(start_year_raw) if start_year_raw is not None else end_year
            start_month: int = _MONTHS[start_month_name.lower()]

            months: int = (end_year - start_year) * 12 + (end_month - start_month)
            if months > 0:
                total_months += months

        return math.floor(total_months / 12)
