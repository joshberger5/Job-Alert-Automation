import os

from infrastructure.job_fetchers import JobFetcher
from infrastructure.job_fetchers.adzuna_fetcher import AdzunaFetcher
from infrastructure.job_fetchers.adzuna_similar_fetcher import AdzunaSimilarFetcher
from infrastructure.job_fetchers.greenhouse_fetcher import GreenhouseFetcher
from infrastructure.job_fetchers.landstar_fetcher import LandstarFetcher
from infrastructure.job_fetchers.lever_fetcher import LeverFetcher
from infrastructure.job_fetchers.workday_fetcher import WorkdayFetcher
from infrastructure.job_fetchers.boa_fetcher import BankOfAmericaFetcher
from infrastructure.job_fetchers.icims_fetcher import IcimsFetcher, IcimsSitemapFetcher
from infrastructure.job_fetchers.remoteok_fetcher import RemoteOKFetcher
from infrastructure.job_fetchers.weworkremotely_fetcher import WeWorkRemotelyFetcher


def build_fetchers() -> tuple[list[JobFetcher], list[str]]:
    warnings: list[str] = []
    fetchers_list: list[JobFetcher] = [
        # ── Adzuna ────────────────────────────────────────────────────────────
        AdzunaFetcher(
            app_id=os.environ["ADZUNA_APP_ID"],
            app_key=os.environ["ADZUNA_APP_KEY"],
        ),
        AdzunaFetcher(
            app_id=os.environ["ADZUNA_APP_ID"],
            app_key=os.environ["ADZUNA_APP_KEY"],
            keywords="java remote",
            location="United States",
            max_days_old=3,
        ),
        AdzunaSimilarFetcher(
            app_id=os.environ["ADZUNA_APP_ID"],
            app_key=os.environ["ADZUNA_APP_KEY"],
        ),
        # ── Remote-first boards ───────────────────────────────────────────────
        RemoteOKFetcher(),
        WeWorkRemotelyFetcher(),
        # ── Greenhouse ────────────────────────────────────────────────────────
        GreenhouseFetcher(company="sofi", company_name="SoFi"),
        GreenhouseFetcher(company="robinhood", company_name="Robinhood"),
        GreenhouseFetcher(company="brex", company_name="Brex"),
        GreenhouseFetcher(company="coinbase", company_name="Coinbase"),
        GreenhouseFetcher(company="doordashusa", company_name="DoorDash"),
        GreenhouseFetcher(company="gusto", company_name="Gusto"),
        GreenhouseFetcher(company="checkr", company_name="Checkr"),
        # ── Lever ─────────────────────────────────────────────────────────────
        LeverFetcher(company="dnb", company_name="Dun & Bradstreet"),
        # ── Workday ───────────────────────────────────────────────────────────
        WorkdayFetcher(
            base_url="https://allstate.wd5.myworkdayjobs.com",
            tenant="allstate",
            company="allstate_careers",
            company_name="Allstate",
            recruiting_base="https://allstate.wd5.myworkdayjobs.com/allstate_careers",
            fetch_descriptions=True,
        ),
        WorkdayFetcher(
            base_url="https://geico.wd1.myworkdayjobs.com",
            tenant="geico",
            company="External",
            company_name="GEICO",
            recruiting_base="https://geico.wd1.myworkdayjobs.com/External",
            fetch_descriptions=True,
        ),
        WorkdayFetcher(
            base_url="https://fis.wd5.myworkdayjobs.com",
            tenant="fis",
            company="SearchJobs",
            company_name="FIS Global",
            recruiting_base="https://fis.wd5.myworkdayjobs.com/SearchJobs",
            search_text="java",
        ),
        WorkdayFetcher(
            base_url="https://wd1.myworkdaysite.com",
            tenant="ssctech",
            company="SSCTechnologies",
            company_name="SSC Technologies",
            recruiting_base="https://wd1.myworkdaysite.com/recruiting/ssctech/SSCTechnologies",
            fetch_descriptions=True,
            location_ids=["b5aa81dc192f01dee656c4c5ce2312b9"],
        ),
        WorkdayFetcher(
            base_url="https://vystarcu.wd1.myworkdayjobs.com",
            tenant="vystarcu",
            company="Careers",
            company_name="VyStar Credit Union",
            recruiting_base="https://vystarcu.wd1.myworkdayjobs.com/Careers",
            search_text="",
            fetch_descriptions=True,
            location_ids=["9c1a239b35bd4598856e5393b249b8a1"],
        ),
        # ── Landstar System ──────────────────────────────────────────────────
        LandstarFetcher(),
        # ── Bank of America ───────────────────────────────────────────────────
        BankOfAmericaFetcher(location="Jacksonville, FL"),
        BankOfAmericaFetcher(location="Jacksonville, FL", keywords="Java"),
        # ── iCIMS ─────────────────────────────────────────────────────────────
        IcimsFetcher(base_url="https://jobs.paysafe.com", company_name="Paysafe"),
        IcimsSitemapFetcher(
            base_url="https://careers-fnf.icims.com",
            company_name="FNF",
            location_filter=None,
        ),
    ]

    jsearch_key: str | None = os.environ.get("JSEARCH_API_KEY")
    if jsearch_key:
        try:
            from infrastructure.job_fetchers.jsearch_fetcher import JSearchFetcher  # type: ignore[import-not-found]
            fetchers_list.extend([
                JSearchFetcher(api_key=jsearch_key, query="java developer Jacksonville FL"),
                JSearchFetcher(api_key=jsearch_key, query="java developer remote"),
            ])
        except ImportError:
            warnings.append("JSearchFetcher not yet implemented")
    else:
        warnings.append("JSEARCH_API_KEY not set — JSearch fetcher skipped")

    return fetchers_list, warnings
