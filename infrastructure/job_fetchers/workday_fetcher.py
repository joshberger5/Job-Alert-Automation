import re
import html as html_module
import json as _json
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from domain.job import Job
from infrastructure.job_fetchers._utils import infer_remote

_DETAIL_TIMEOUT: int = 8
_DETAIL_WORKERS: int = 10


class WorkdayFetcher:
    LIMIT = 20

    def __init__(self, base_url: str, tenant: str, company: str,
                 company_name: str, recruiting_base: str,
                 search_text: str = "java", fetch_descriptions: bool = False,
                 location_ids: list[str] | None = None) -> None:
        self.base_url: str = base_url
        self.tenant: str = tenant
        self.company: str = company
        self.company_name: str = company_name
        self.recruiting_base: str = recruiting_base
        self.search_text: str = search_text
        self.fetch_descriptions: bool = fetch_descriptions
        self.location_ids: list[str] | None = location_ids

    def _fetch_description(self, url: str) -> str:
        try:
            resp = requests.get(url, timeout=_DETAIL_TIMEOUT, headers={"Accept": "text/html"})
            resp.raise_for_status()
            match = re.search(
                r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
                resp.text, re.DOTALL
            )
            if not match:
                return ""
            ld = _json.loads(match.group(1))
            raw = ld.get("description", "")
            clean = re.sub(r"<[^>]+>", " ", raw)
            return html_module.unescape(clean).strip()
        except Exception:
            return ""

    def fetch(self) -> list[Job]:
        # Collect all postings first (pagination is sequential)
        raw_postings: list[tuple[dict, str | None]] = []
        offset = 0

        while True:
            body: dict[str, object] = {
                "appliedFacets": {},
                "limit": self.LIMIT,
                "offset": offset,
                "searchText": self.search_text,
            }
            if self.location_ids is not None:
                body["locations"] = self.location_ids
            response = requests.post(
                f"{self.base_url}/wday/cxs/{self.tenant}/{self.company}/jobs",
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            postings = data.get("jobPostings", [])
            for item in postings:
                external_path = item.get("externalPath", "")
                url: str | None = f"{self.recruiting_base}{external_path}" if external_path else None
                raw_postings.append((item, url))

            if len(postings) < self.LIMIT:
                break
            offset += self.LIMIT

        # Fetch descriptions in parallel if requested
        descriptions: dict[str | None, str] = {}
        if self.fetch_descriptions:
            urls_to_fetch: list[str] = [url for _, url in raw_postings if url]
            with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as pool:
                future_to_url = {pool.submit(self._fetch_description, url): url for url in urls_to_fetch}
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        descriptions[url] = future.result()
                    except Exception:
                        descriptions[url] = ""

        jobs: list[Job] = []
        for item, url in raw_postings:
            bullet_fields: list = item.get("bulletFields") or []
            job_id: str = bullet_fields[0] if bullet_fields else ""
            locations_text: str = item.get("locationsText", "")
            remote: bool | None = infer_remote(locations_text)
            description: str = descriptions.get(url, "") if self.fetch_descriptions else ""

            jobs.append(Job(
                id=job_id,
                title=item.get("title", ""),
                company=self.company_name,
                location=locations_text,
                description=description,
                salary=None,
                url=url,
                required_skills=[],
                remote=remote,
                employment_type=None,
            ))

        return jobs
