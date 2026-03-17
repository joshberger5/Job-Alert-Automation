import html as _html
import os
import smtplib
import urllib.parse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from application.job_record import JobRecord

_FEEDBACK_BASE_URL: str = (
    "https://joshberger5.github.io/Job-Alert-Automation/feedback.html"
)


def _score_color(score: int) -> str:
    if score >= 14:
        return "#16a34a"
    if score >= 10:
        return "#2563eb"
    if score >= 7:
        return "#d97706"
    return "#94a3b8"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    return f"{seconds / 60:.1f}m"


def _vote_links(
    base_url: str,
    job_id: str,
    title: str,
    company: str,
    pat: str,
) -> tuple[str, str]:
    """Return (thumbs_up_url, thumbs_down_url) for the feedback page."""
    def _build(vote: str) -> str:
        qs: str = urllib.parse.urlencode({
            "job_id": job_id,
            "vote": vote,
            "title": title,
            "company": company,
        })
        return f"{base_url}?{qs}#{pat}"
    return _build("+1"), _build("-1")


def _job_card(job: JobRecord) -> str:
    title: str = job.get("title", "Untitled")
    company: str = job.get("company", "")
    location: str = job.get("location", "")
    salary: str | None = job.get("salary")
    score: int = job.get("score", 0)
    url: str | None = job.get("url")
    remote: bool | None = job.get("remote")
    emp_type: str | None = job.get("employment_type")

    display_location: str = location if location else ("Remote" if remote else "")
    meta_parts: list[str] = []
    if display_location:
        meta_parts.append(f"&#128205; {display_location}")
    if emp_type:
        meta_parts.append(emp_type.replace("-", " ").title())
    meta_line: str = " &nbsp;&middot;&nbsp; ".join(meta_parts) if meta_parts else "&nbsp;"

    salary_row: str = (
        f'<p style="margin:5px 0 0;color:#475569;font-size:13px;">&#128176; {salary}</p>'
        if salary else ""
    )

    btn: str = (
        f'<a href="{url}" style="display:inline-block;padding:9px 22px;background:#3b82f6;'
        f'color:white;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600;">'
        f'View Job &#8594;</a>'
        if url else ""
    )

    pat: str = os.environ.get("FEEDBACK_PAT", "")
    job_id: str = job.get("id", "")
    vote_row: str = ""
    if pat and job_id:
        up_url: str
        down_url: str
        up_url, down_url = _vote_links(
            _FEEDBACK_BASE_URL, job_id, title, company, pat
        )
        _thumb_up: str = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"'
            ' fill="#3b82f6" style="vertical-align:middle;margin-right:3px;">'
            '<path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32'
            'c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10'
            'c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05'
            'c.09-.23.14-.47.14-.73v-2z"/></svg>'
        )
        _thumb_down: str = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"'
            ' fill="#3b82f6" style="vertical-align:middle;margin-right:3px;">'
            '<path d="M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2'
            'c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L10.83 23'
            'l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z"/></svg>'
        )
        vote_row = (
            f'<p style="margin:8px 0 0;font-size:13px;">'
            f'<a href="{up_url}" style="text-decoration:none;margin-right:12px;">{_thumb_up} Relevant</a>'
            f'<a href="{down_url}" style="text-decoration:none;color:#64748b;">{_thumb_down} Not relevant</a>'
            f'</p>'
        )

    color: str = _score_color(score)

    return f"""
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:white;border-radius:8px;margin-bottom:10px;
              border:1px solid #e2e8f0;border-left:4px solid {color};">
  <tr>
    <td style="padding:18px 22px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="vertical-align:top;">
            <p style="margin:0;color:#64748b;font-size:11px;font-weight:600;
                      letter-spacing:0.5px;text-transform:uppercase;">{company}</p>
            <p style="margin:5px 0 0;color:#0f172a;font-size:17px;
                      font-weight:700;line-height:1.3;">{title}</p>
          </td>
          <td style="vertical-align:top;text-align:right;white-space:nowrap;padding-left:12px;">
            <span style="display:inline-block;background:{color};color:white;
                         border-radius:20px;padding:4px 12px;font-size:13px;font-weight:700;">
              {score}
            </span>
          </td>
        </tr>
        <tr>
          <td colspan="2" style="padding-top:10px;">
            <p style="margin:0;color:#475569;font-size:13px;">{meta_line}</p>
            {salary_row}
          </td>
        </tr>
        <tr>
          <td colspan="2" style="padding-top:14px;">{btn}{vote_row}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _section(
    comment: str,
    heading: str,
    subtext: str,
    jobs: list[JobRecord],
) -> str:
    n: int = len(jobs)
    s: str = "s" if n != 1 else ""
    sorted_jobs: list[JobRecord] = sorted(jobs, key=lambda j: j.get("score", 0), reverse=True)
    if sorted_jobs:
        body: str = "\n".join(_job_card(j) for j in sorted_jobs)
    else:
        body = """<table width="100%" cellpadding="0" cellspacing="0"
       style="background:white;border-radius:8px;border:1px solid #e2e8f0;">
  <tr>
    <td style="padding:24px;text-align:center;">
      <p style="margin:0;color:#64748b;font-size:14px;">No jobs in this section.</p>
    </td>
  </tr>
</table>"""
    return f"""
        <!-- {comment} -->
        <tr>
          <td style="padding:20px 24px 4px;border-top:2px solid #e2e8f0;">
            <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#475569;
                      letter-spacing:0.8px;text-transform:uppercase;">
              {heading}
              &nbsp;<span style="color:#94a3b8;font-weight:400;text-transform:none;
                                 letter-spacing:0;">({n} job{s})</span>
            </p>
            <p style="margin:0 0 12px;color:#94a3b8;font-size:11px;">{subtext}</p>
            {body}
          </td>
        </tr>"""


def _build_html(
    jobs: list[JobRecord],
    run_at: datetime,
    duration_s: float,
    total_fetched: int,
    llm_relevant_jobs: list[JobRecord] | None = None,
    llm_filtered_jobs: list[JobRecord] | None = None,
    run_log: str = "",
) -> str:
    n: int = len(jobs)
    s: str = "s" if n != 1 else ""
    date_str: str = run_at.strftime("%b %d, %Y at %H:%M")
    duration_str: str = _fmt_duration(duration_s)

    sorted_jobs: list[JobRecord] = sorted(jobs, key=lambda j: j.get("score", 0), reverse=True)

    if n == 0:
        cards_html: str = """
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:white;border-radius:8px;border:1px solid #e2e8f0;">
  <tr>
    <td style="padding:36px;text-align:center;">
      <p style="margin:0;color:#64748b;font-size:15px;">No qualified jobs this run.</p>
    </td>
  </tr>
</table>"""
    else:
        inner: str = "\n".join(_job_card(j) for j in sorted_jobs)
        cards_html = f"""<p style="margin:0 0 14px;font-size:11px;font-weight:700;color:#475569;
          letter-spacing:0.8px;text-transform:uppercase;">
  Qualified Jobs
  &nbsp;<span style="color:#94a3b8;font-weight:400;text-transform:none;
                     letter-spacing:0;">({n} job{s})</span>
</p>
{inner}"""

    llm_rejected_html: str = _section(
        comment="LLM-FILTERED SECTION",
        heading="LLM Rejected &mdash; scored but flagged as irrelevant",
        subtext=(
            "These reached the scoring minimum but the LLM considered the title "
            "outside your field. Review to catch false rejections."
        ),
        jobs=llm_filtered_jobs or [],
    )
    llm_relevant_html: str = _section(
        comment="LLM-RELEVANT SECTION",
        heading="Possibly Relevant &mdash; scored below threshold",
        subtext=(
            "These passed location/remote filtering and the LLM title check, "
            "but didn&rsquo;t reach the scoring minimum."
        ),
        jobs=llm_relevant_jobs or [],
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Job Alert</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:24px 0;">
  <tr>
    <td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="max-width:600px;width:100%;">

        <!-- HEADER -->
        <tr>
          <td style="background:#0f172a;border-radius:12px 12px 0 0;padding:28px 32px 22px;">
            <p style="margin:0;color:#475569;font-size:11px;letter-spacing:1px;
                      text-transform:uppercase;font-weight:600;">Job Alert</p>
            <h1 style="margin:6px 0 0;color:white;font-size:26px;font-weight:700;line-height:1.2;">
              {n} Qualified Job{s}
            </h1>
            <p style="margin:8px 0 0;color:#475569;font-size:13px;">{date_str}</p>
          </td>
        </tr>

        <!-- STATS BAR -->
        <tr>
          <td style="background:#1e293b;padding:14px 32px;border-radius:0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="color:#94a3b8;font-size:12px;">
                  <span style="color:white;font-weight:700;font-size:18px;">{total_fetched}</span>
                  &nbsp;scanned
                </td>
                <td style="color:#94a3b8;font-size:12px;text-align:center;">
                  <span style="color:#3b82f6;font-weight:700;font-size:18px;">{n}</span>
                  &nbsp;qualified
                </td>
                <td style="color:#94a3b8;font-size:12px;text-align:right;">
                  <span style="color:white;font-weight:700;font-size:18px;">{duration_str}</span>
                  &nbsp;runtime
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- JOB CARDS -->
        <tr>
          <td style="padding:20px 24px 8px;">
            {cards_html}
          </td>
        </tr>

        {llm_rejected_html}

        {llm_relevant_html}

        <!-- RUN LOG SECTION -->
        <tr>
          <td style="padding:20px 24px 4px;border-top:2px solid #e2e8f0;">
            <p style="margin:0 0 8px;font-size:11px;font-weight:700;color:#475569;
                      letter-spacing:0.8px;text-transform:uppercase;">Run Log</p>
            <pre style="margin:0;background:#0f172a;color:#94a3b8;font-size:11px;
                        font-family:'Courier New',Courier,monospace;padding:16px;
                        border-radius:6px;overflow-x:auto;white-space:pre-wrap;
                        word-break:break-word;">{_html.escape(run_log)}</pre>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="padding:8px 0 28px;text-align:center;">
            <p style="margin:0;color:#94a3b8;font-size:11px;">
              Job Alert Automation &nbsp;&middot;&nbsp; {date_str}
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


class EmailNotifier:

    def __init__(self) -> None:
        self.smtp_host: str = os.environ["SMTP_HOST"]
        self.smtp_port: int = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user: str = os.environ["SMTP_USER"]
        self.smtp_pass: str = os.environ["SMTP_PASS"]
        self.email_to: str = os.environ["EMAIL_TO"]

    def send(
        self,
        qualified_jobs: list[JobRecord],
        run_at: datetime,
        duration_s: float,
        total_fetched: int,
        llm_relevant_jobs: list[JobRecord] | None = None,
        llm_filtered_jobs: list[JobRecord] | None = None,
        run_log: str = "",
    ) -> None:
        n: int = len(qualified_jobs)
        s: str = "s" if n != 1 else ""
        date_str: str = run_at.strftime("%b %d, %Y")
        subject: str = f"Job Alert: {n} qualified job{s} \u2014 {date_str}"

        html: str = _build_html(
            qualified_jobs, run_at, duration_s, total_fetched,
            llm_relevant_jobs, llm_filtered_jobs, run_log,
        )

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.smtp_user
        msg["To"] = self.email_to
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            server.sendmail(self.smtp_user, self.email_to, msg.as_string())
