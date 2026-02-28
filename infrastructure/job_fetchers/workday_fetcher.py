import re
import html as html_module
import json as _json
import requests
from domain.job import Job


class WorkdayFetcher:
    LIMIT = 20

    def __init__(self, base_url: str, tenant: str, company: str,
                 company_name: str, recruiting_base: str,
                 search_text: str = "java", fetch_descriptions: bool = False):
        self.base_url = base_url
        self.tenant = tenant
        self.company = company
        self.company_name = company_name
        self.recruiting_base = recruiting_base
        self.search_text = search_text
        self.fetch_descriptions = fetch_descriptions

    def _fetch_description(self, url: str) -> str:
        try:
            resp = requests.get(url, timeout=10, headers={"Accept": "text/html"})
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
        jobs: list[Job] = []
        offset = 0

        while True:
            response = requests.post(
                f"{self.base_url}/wday/cxs/{self.tenant}/{self.company}/jobs",
                json={
                    "appliedFacets": {},
                    "limit": self.LIMIT,
                    "offset": offset,
                    "searchText": self.search_text,
                },
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            postings = data.get("jobPostings", [])
            for item in postings:
                bullet_fields = item.get("bulletFields") or []
                job_id = bullet_fields[0] if bullet_fields else ""
                external_path = item.get("externalPath", "")
                url = f"{self.recruiting_base}{external_path}" if external_path else None

                locations_text = item.get("locationsText", "")
                remote = True if "remote" in locations_text.lower() else None

                description = self._fetch_description(url) if self.fetch_descriptions and url else ""

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

            if len(postings) < self.LIMIT:
                break
            offset += self.LIMIT

        return jobs
