import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _score_color(score: int) -> str:
    if score >= 14:
        return "#16a34a"
    if score >= 10:
        return "#2563eb"
    return "#d97706"


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    return f"{seconds / 60:.1f}m"


def _job_card(job: dict) -> str:
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
          <td colspan="2" style="padding-top:14px;">{btn}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>"""


def _build_html(
    jobs: list[dict],
    run_at: datetime,
    duration_s: float,
    total_fetched: int,
) -> str:
    n: int = len(jobs)
    s: str = "s" if n != 1 else ""
    date_str: str = run_at.strftime("%b %d, %Y at %H:%M")
    duration_str: str = _fmt_duration(duration_s)

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
        cards_html = "\n".join(_job_card(j) for j in jobs)

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
        qualified_jobs: list[dict],
        run_at: datetime,
        duration_s: float,
        total_fetched: int,
    ) -> None:
        n: int = len(qualified_jobs)
        s: str = "s" if n != 1 else ""
        date_str: str = run_at.strftime("%b %d, %Y")
        subject: str = f"Job Alert: {n} qualified job{s} \u2014 {date_str}"

        html: str = _build_html(qualified_jobs, run_at, duration_s, total_fetched)

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
