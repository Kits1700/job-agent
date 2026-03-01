"""
Daily email reporter — sends summary email with:
1. The daily report DOCX (top 10 jobs + cover letters)
2. Each cover letter as a separate .txt file (easy copy-paste)
3. Your resume PDF
"""
import logging
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

logger = logging.getLogger("job_agent.reporter")


def _attach_file(msg: MIMEMultipart, filepath: str, filename: str = None):
    """Attach a file to the email message."""
    path = Path(filepath)
    if not path.exists():
        logger.warning(f"Attachment not found: {filepath}")
        return False

    fname = filename or path.name
    ext = path.suffix.lower()

    # Pick MIME type
    mime_types = {
        ".pdf": ("application", "pdf"),
        ".docx": ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ".txt": ("text", "plain"),
    }
    maintype, subtype = mime_types.get(ext, ("application", "octet-stream"))

    with open(path, "rb") as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename=\"{fname}\"")
        msg.attach(part)

    logger.info(f"  📎 Attached: {fname}")
    return True


def send_daily_report(
    jobs: list[dict],
    total_discovered: int,
    config: dict,
    attachment_path: str = None,
    cover_letter_dir: str = None,
):
    """Send daily email with summary + all attachments."""
    email_cfg = config.get("email_report", {})
    if not email_cfg.get("enabled"):
        logger.info("Email reporting disabled — skipping")
        return

    if not email_cfg.get("sender_password"):
        logger.warning("⚠️  No email password configured — skipping email. Check config.yaml")
        return

    today = datetime.now().strftime("%A, %d %B %Y")
    candidate_name = config.get("candidate", {}).get("name", "")
    resume_path = config.get("paths", {}).get("resume", "")

    # ── Build HTML email body ──
    job_rows = ""
    for i, job in enumerate(jobs):
        score = job.get("score", 0)
        score_color = "#2ecc71" if score >= 7 else "#f39c12" if score >= 5 else "#e74c3c"
        job_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{i+1}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                <a href="{job.get('url','#')}" style="color:#e94560;text-decoration:none;font-weight:bold;">
                    {job.get('title','')}
                </a>
            </td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{job.get('company','')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{job.get('location','')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:center;">
                <span style="background:{score_color};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px;">{score}/10</span>
            </td>
        </tr>"""

    # Build attachment list for the email body
    attachment_list = ""
    attachment_list += "<li><strong>📄 Full Report (Word doc)</strong> — All jobs with fit analysis + cover letters</li>"
    attachment_list += f"<li><strong>📋 Your Resume (PDF)</strong> — {Path(resume_path).name if resume_path else 'resume.pdf'}</li>"
    if jobs:
        attachment_list += f"<li><strong>✉️ {len(jobs)} Cover Letters (.txt)</strong> — One per job, ready to copy-paste</li>"

    html = f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#333;max-width:650px;margin:0 auto;padding:20px;">
        <h1 style="color:#1a1a2e;border-bottom:2px solid #e94560;padding-bottom:10px;">
            Daily Job Report — {today}
        </h1>
        <p style="color:#666;">Hi {candidate_name.split()[0] if candidate_name else 'there'},</p>
        <p>Found <strong>{total_discovered}</strong> new jobs today. Here are your <strong>top {len(jobs)}</strong> matches:</p>

        <table style="width:100%;border-collapse:collapse;margin:20px 0;">
            <tr style="background:#1a1a2e;color:#fff;">
                <th style="padding:10px;text-align:left;">#</th>
                <th style="padding:10px;text-align:left;">Role</th>
                <th style="padding:10px;text-align:left;">Company</th>
                <th style="padding:10px;text-align:left;">Location</th>
                <th style="padding:10px;text-align:center;">Score</th>
            </tr>
            {job_rows}
        </table>

        <h2 style="color:#1a1a2e;margin-top:30px;">📎 Attachments</h2>
        <ul style="line-height:1.8;">
            {attachment_list}
        </ul>

        <p style="margin-top:20px;padding:12px;background:#f0f7ff;border-radius:8px;border-left:3px solid #e94560;">
            <strong>How to use:</strong> Open the report doc to review jobs. Click "Apply Here" links.
            Copy the cover letter from the matching .txt file (or from the doc) and paste it into the application.
            Attach your resume PDF. Done!
        </p>

        <hr style="border:none;border-top:1px solid #eee;margin:30px 0;"/>
        <p style="color:#999;font-size:12px;">
            Job Agent · Ran at {datetime.now().strftime('%H:%M')} · {total_discovered} discovered · {len(jobs)} in report
        </p>
    </body>
    </html>
    """

    # ── Build and send email ──
    try:
        msg = MIMEMultipart()
        msg["Subject"] = f"🎯 {len(jobs)} Jobs Ready to Apply — {today}"
        msg["From"] = email_cfg["sender_email"]
        msg["To"] = email_cfg["recipient_email"]
        msg.attach(MIMEText(html, "html"))

        logger.info("📎 Attaching files to email...")

        # 1. Attach the main report DOCX
        if attachment_path:
            _attach_file(msg, attachment_path)

        # 2. Attach resume PDF
        if resume_path and Path(resume_path).exists():
            _attach_file(msg, resume_path)
        else:
            logger.warning(f"Resume not found at: {resume_path}")

        # 3. Attach individual cover letters
        if cover_letter_dir and Path(cover_letter_dir).exists():
            cl_files = sorted(Path(cover_letter_dir).glob("cover_letter_*.txt"))
            for cl_file in cl_files:
                _attach_file(msg, str(cl_file))
        else:
            # Fallback: create cover letter files from job data and attach them
            for i, job in enumerate(jobs):
                cl_text = job.get("cover_letter", "")
                if not cl_text or cl_text.startswith("("):
                    continue

                # Create a nicely formatted cover letter file
                company = job.get("company", "Unknown").replace(" ", "_").replace("/", "-")
                title = job.get("title", "Unknown").replace(" ", "_").replace("/", "-")[:30]
                fname = f"CoverLetter_{i+1}_{company}_{title}.txt"

                header = (
                    f"Cover Letter for: {job.get('title', '')}\n"
                    f"Company: {job.get('company', '')}\n"
                    f"Location: {job.get('location', '')}\n"
                    f"Apply: {job.get('url', '')}\n"
                    f"Score: {job.get('score', 0)}/10\n"
                    f"{'='*60}\n\n"
                )

                part = MIMEBase("text", "plain")
                part.set_payload((header + cl_text).encode("utf-8"))
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename=\"{fname}\"")
                msg.attach(part)
                logger.info(f"  📎 Attached: {fname}")

        # Send
        with smtplib.SMTP(email_cfg["smtp_server"], email_cfg["smtp_port"]) as server:
            server.starttls()
            server.login(email_cfg["sender_email"], email_cfg["sender_password"])
            server.sendmail(
                email_cfg["sender_email"],
                email_cfg["recipient_email"],
                msg.as_string(),
            )

        logger.info(f"📧 Email sent to {email_cfg['recipient_email']}")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
