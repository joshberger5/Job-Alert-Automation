import re
import json as _json
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any

import requests
from bs4 import BeautifulSoup

from domain.job import Job
from infrastructure.job_fetchers._utils import infer_remote

_LISTING_TIMEOUT: int = 10
_DETAIL_TIMEOUT: int = 12
_DETAIL_BATCH_TIMEOUT: int = 120
_DETAIL_WORKERS: int = 10
_LIMIT: int = 25
_ICE_PATH: str = "/hcmRestApi/resources/11.13.18.05/recruitingICEJobRequisitions"


class OracleFetcher:
    """Fetcher for Oracle Cloud HCM career sites using the ICE REST endpoint."""

    def __init__(
        self,
        base_url: str,
        site_id: str,
        company_name: str,
        keyword: str,
    ) -> None:
        self._base_url: str = base_url.rstrip("/")
        self._site_id: str = site_id
        self.company_name: str = company_name
        self._keyword: str = keyword

    def fetch(self) -> list[Job]:
        req_dicts: list[dict[str, Any]] = []
        offset: int = 0
        while True:
            items: list[dict[str, Any]]
            has_more: bool
            items, has_more = self._fetch_listing_page(offset)
            for item in items:
                reqs: list[dict[str, Any]] = item.get("requisitionList", [])
                req_dicts.extend(reqs)
            if not has_more:
                break
            offset += _LIMIT

        req_ids: list[str] = [str(r.get("Id", "")) for r in req_dicts if r.get("Id")]
        descriptions: dict[str, str] = self._fetch_all_details(req_ids)

        jobs: list[Job] = []
        for req in req_dicts:
            req_id: str = str(req.get("Id", ""))
            location: str = str(req.get("PrimaryLocation", ""))
            url: str = (
                f"{self._base_url}/hcmUI/CandidateExperience/en/sites"
                f"/{self._site_id}/job/{req_id}"
            )
            description: str = descriptions.get(req_id, "")
            jobs.append(
                Job(
                    id=req_id,
                    title=str(req.get("Title", "")),
                    company=self.company_name,
                    location=location,
                    description=description,
                    salary=None,
                    url=url,
                    required_skills=[],
                    remote=infer_remote(location),
                    employment_type=None,
                )
            )
        return jobs

    def _fetch_listing_page(
        self, offset: int
    ) -> tuple[list[dict[str, Any]], bool]:
        params: dict[str, str] = {
            "finder": f"findReqs;keyword={self._keyword};limit={_LIMIT};offset={offset}",
            "expand": "requisitionList",
            "onlyData": "true",
        }
        resp: requests.Response = requests.get(
            f"{self._base_url}{_ICE_PATH}",
            params=params,
            timeout=_LISTING_TIMEOUT,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        items: list[dict[str, Any]] = data.get("items", [])
        has_more: bool = bool(data.get("hasMore", False))
        return items, has_more

    def _fetch_all_details(self, req_ids: list[str]) -> dict[str, str]:
        descriptions: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as pool:
            future_to_id: dict[Future[str], str] = {
                pool.submit(self._fetch_detail, req_id): req_id for req_id in req_ids
            }
            done, not_done = wait(future_to_id, timeout=_DETAIL_BATCH_TIMEOUT)
            for f in not_done:
                f.cancel()
            for f in done:
                req_id: str = future_to_id[f]
                try:
                    descriptions[req_id] = f.result()
                except Exception:
                    descriptions[req_id] = ""
        return descriptions

    def _fetch_detail(self, req_id: str) -> str:
        url: str = (
            f"{self._base_url}/hcmUI/CandidateExperience/en/sites"
            f"/{self._site_id}/job/{req_id}"
        )
        try:
            resp: requests.Response = requests.get(url, timeout=_DETAIL_TIMEOUT)
            resp.raise_for_status()
        except Exception:
            return ""

        # Try JSON-LD first
        match: re.Match[str] | None = re.search(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            resp.text,
            re.DOTALL,
        )
        if match:
            try:
                ld: dict[str, Any] = _json.loads(match.group(1))
                raw: str = ld.get("description", "")
                if raw:
                    clean: str = re.sub(r"<[^>]+>", " ", raw)
                    return clean.strip()
            except Exception:
                pass

        # Fall back to BeautifulSoup text extraction
        soup: BeautifulSoup = BeautifulSoup(resp.text, "html.parser")
        main_div = soup.select_one("div[data-bind*='description'], div.job-description, main")
        if main_div:
            return main_div.get_text(separator=" ", strip=True)
        return soup.get_text(separator=" ", strip=True)[:2000]
