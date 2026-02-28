import requests
from domain.job import Job

BOA_BASE = "https://careers.bankofamerica.com"


class BankOfAmericaFetcher:
    ROWS = 50

    def __init__(self, location: str = "Jacksonville, FL"):
        self.location = location

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        start = 0

        while True:
            response = requests.get(
                f"{BOA_BASE}/services/jobssearchservlet",
                params={
                    "start": start,
                    "rows": self.ROWS,
                    "search": "jobsByLocation",
                    "searchstring": self.location,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            listings = data.get("jobsList", [])
            for item in listings:
                jcr_url = item.get("jcrURL", "")
                job_id = jcr_url
                url = f"{BOA_BASE}{jcr_url}" if jcr_url else None

                family = item.get("family", "")
                lob = item.get("lob", "")
                description = " | ".join(filter(None, [family, lob]))

                jobs.append(Job(
                    id=job_id,
                    title=item.get("postingTitle", ""),
                    company="Bank of America",
                    location=item.get("location", ""),
                    description=description,
                    salary=None,
                    url=url,
                    required_skills=[],
                ))

            if len(listings) < self.ROWS:
                break
            start += self.ROWS

        return jobs
