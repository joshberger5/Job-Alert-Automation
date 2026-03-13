# ATS Research — New Company Fetchers

Investigation findings for companies added in Phase 2 (02-05).

## Summary Table

| Company | ATS | Implementation | Status |
|---|---|---|---|
| JPMorgan Chase | Oracle Cloud HCM | OracleFetcher | ✅ Implemented |
| CSX Transportation | Oracle Cloud HCM | OracleFetcher | ✅ Implemented |
| Florida Blue | Oracle Cloud HCM | OracleFetcher | ✅ Implemented |
| Availity | Workday | WorkdayFetcher | ✅ Implemented |

---

## JPMorgan Chase

- **Careers URL**: https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001
- **ATS identified**: Oracle Cloud HCM — evident from `jpmc.fa.oraclecloud.com` domain and `/hcmUI/CandidateExperience/` path pattern
- **Decision**: Implemented via `OracleFetcher`
- **Rationale**: Oracle Cloud HCM ICE endpoint (`/hcmRestApi/resources/11.13.18.05/recruitingICEJobRequisitions`) is unauthenticated for public career sites (see Oracle ICE Endpoint Notes below)
- **Implementation config**:
  ```python
  OracleFetcher(
      base_url="https://jpmc.fa.oraclecloud.com",
      site_id="CX_1001",
      company_name="JPMorgan Chase",
      keyword="java",
  )
  ```

---

## CSX Transportation

- **Careers URL**: https://fa-eowa-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CSXCareers
- **ATS identified**: Oracle Cloud HCM — evident from `fa-eowa-saasfaprod1.fa.ocs.oraclecloud.com` domain (Oracle SaaS platform domain) and `/hcmUI/CandidateExperience/` path
- **Decision**: Implemented via `OracleFetcher`
- **Rationale**: Uses the same Oracle Cloud HCM infrastructure as JPMC; same unauthenticated ICE endpoint pattern applies
- **Implementation config**:
  ```python
  OracleFetcher(
      base_url="https://fa-eowa-saasfaprod1.fa.ocs.oraclecloud.com",
      site_id="CSXCareers",
      company_name="CSX",
      keyword="java",
  )
  ```

---

## Florida Blue (GuideWell)

- **Careers URL**: https://careers.floridablue.com → redirects to https://fa-etum-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/en/sites/floridablue
- **ATS identified**: Oracle Cloud HCM — the careers.floridablue.com domain redirects to an Oracle SaaS platform URL (`fa-etum-saasfaprod1.fa.ocs.oraclecloud.com`)
- **Decision**: Implemented via `OracleFetcher`
- **Rationale**: Same Oracle Cloud HCM pattern; redirect confirms Oracle ATS without needing to inspect page source
- **Implementation config**:
  ```python
  OracleFetcher(
      base_url="https://fa-etum-saasfaprod1.fa.ocs.oraclecloud.com",
      site_id="floridablue",
      company_name="Florida Blue",
      keyword="java",
  )
  ```

---

## Availity

- **Careers URL**: https://availity.wd1.myworkdayjobs.com/Availity_Careers_US
- **ATS identified**: Workday — evident from `availity.wd1.myworkdayjobs.com` domain (Workday standard subdomain pattern)
- **Decision**: Implemented via existing `WorkdayFetcher`
- **Rationale**: Workday ATS is already fully supported; no new fetcher class required
- **Implementation config**:
  ```python
  WorkdayFetcher(
      base_url="https://availity.wd1.myworkdayjobs.com",
      tenant="availity",
      company="Availity_Careers_US",
      company_name="Availity",
      recruiting_base="https://availity.wd1.myworkdayjobs.com/Availity_Careers_US",
      fetch_descriptions=True,
  )
  ```

---

## Oracle ICE Endpoint Notes

The Oracle ICE (Intelligent Career Experience) REST endpoint is **unauthenticated** for public career sites.

- **Endpoint**: `{base_url}/hcmRestApi/resources/11.13.18.05/recruitingICEJobRequisitions`
- **Auth required**: No — public GET with `finder=findReqs;keyword=...` parameters
- **Evidence**: This is the standard Oracle Cloud HCM public career portal API. Oracle designed it to be accessible without authentication for external candidates browsing jobs. The `/hcmUI/CandidateExperience/` frontend itself calls this endpoint client-side.
- **Fallback**: If a specific instance returns HTTP 401/403, `OracleFetcher._fetch_listing_page()` will raise on `resp.raise_for_status()`, causing the fetcher to fail gracefully via the retry/failure pipeline.

Detail pages (`/hcmUI/CandidateExperience/en/sites/{site_id}/job/{req_id}`) are also publicly accessible and may embed JSON-LD (`application/ld+json`) with job description data. `OracleFetcher._fetch_detail()` attempts JSON-LD extraction first and falls back to BeautifulSoup HTML extraction.
