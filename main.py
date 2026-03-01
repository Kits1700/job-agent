"""
main.py — Job Agent Orchestrator (Report Mode)

Runs daily:
1. Scrape jobs from LinkedIn, Indeed, Greenhouse, Lever
2. Score & rank using Claude
3. Generate tailored cover letters for top 10
4. Generate a Word doc with everything you need to apply manually
5. Email you the report + cover letters + resume attached
"""
import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

from database import JobDatabase
from scrapers import scrape_all
from ai_module import score_job, generate_cover_letter, tailor_resume_summary
from reporter import send_daily_report

# ─────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────

def setup_logging(logs_dir: str):
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(logs_dir) / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("job_agent")


# ─────────────────────────────────────────────────
# Load config
# ─────────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        config = yaml.safe_load(f)

    api_key = config.get("api_keys", {}).get("anthropic")
    if api_key and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = api_key

    return config


def load_resume(config: dict) -> str:
    resume_text_path = config["paths"]["resume_text"]
    if not Path(resume_text_path).exists():
        print(f"\n⚠️  Please create {resume_text_path} with your resume in plain text.")
        sys.exit(1)
    return Path(resume_text_path).read_text()


# ─────────────────────────────────────────────────
# Generate daily report DOCX
# ─────────────────────────────────────────────────

def generate_report_docx(top_jobs: list[dict], output_path: str):
    """Generate a professional Word doc with top 10 jobs, cover letters, and links."""

    today = datetime.now().strftime("%A, %d %B %Y")
    js_file = Path(output_path).with_suffix(".js")

    def esc(text: str) -> str:
        if not text:
            return ""
        return (str(text)
                .replace("\\", "\\\\")
                .replace("`", "\\`")
                .replace("${", "\\${")
                .replace("\r", ""))

    # Build job sections
    job_sections = ""
    for i, job in enumerate(top_jobs):
        score = job.get("score", 0)
        title = esc(job.get("title", "Unknown"))
        company = esc(job.get("company", "Unknown"))
        location = esc(job.get("location", "N/A"))
        url = esc(job.get("url", ""))
        reasons = esc(job.get("score_reasons", ""))
        concerns = esc(job.get("score_concerns", ""))
        cover_letter = esc(job.get("cover_letter", ""))
        source = esc(job.get("source", ""))
        role_cat = esc(job.get("role_category", ""))

        cl_paragraphs = ""
        if cover_letter:
            for para in cover_letter.split("\\n"):
                para = para.strip()
                if para:
                    cl_paragraphs += f"""
            new Paragraph({{
                spacing: {{ after: 120 }},
                children: [new TextRun({{ text: `{para}`, font: "Arial", size: 22 }})]
            }}),"""

        job_sections += f"""
        // ── JOB {i+1} ──
        new Paragraph({{ pageBreakBefore: {str(i > 0).lower()}, children: [] }}),
        new Paragraph({{
            spacing: {{ before: 120, after: 60 }},
            children: [
                new TextRun({{ text: "Job {i+1}: ", font: "Arial", size: 28, bold: true, color: "E94560" }}),
                new TextRun({{ text: `{title}`, font: "Arial", size: 28, bold: true }}),
            ]
        }}),
        new Paragraph({{
            spacing: {{ after: 60 }},
            children: [
                new TextRun({{ text: `{company}`, font: "Arial", size: 24, bold: true, color: "333333" }}),
                new TextRun({{ text: `  |  {location}  |  {source.upper()}  |  Score: {score}/10`, font: "Arial", size: 22, color: "666666" }}),
            ]
        }}),
        new Paragraph({{
            spacing: {{ after: 120 }},
            children: [new ExternalHyperlink({{
                children: [new TextRun({{ text: "Apply Here", style: "Hyperlink", font: "Arial", size: 22 }})],
                link: `{url}`,
            }})]
        }}),
        new Paragraph({{
            spacing: {{ before: 160, after: 60 }},
            children: [new TextRun({{ text: "Why This Is a Good Fit", font: "Arial", size: 24, bold: true, color: "1A1A2E" }})]
        }}),
        new Paragraph({{
            spacing: {{ after: 60 }},
            children: [new TextRun({{ text: `{reasons}`, font: "Arial", size: 22 }})]
        }}),
        new Paragraph({{
            spacing: {{ before: 100, after: 60 }},
            children: [new TextRun({{ text: "Potential Concerns", font: "Arial", size: 24, bold: true, color: "1A1A2E" }})]
        }}),
        new Paragraph({{
            spacing: {{ after: 120 }},
            children: [new TextRun({{ text: `{concerns}`, font: "Arial", size: 22, color: "555555" }})]
        }}),
        new Paragraph({{
            spacing: {{ before: 200, after: 100 }},
            border: {{ bottom: {{ style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }} }},
            children: [new TextRun({{ text: "Tailored Cover Letter (copy-paste ready)", font: "Arial", size: 24, bold: true, color: "1A1A2E" }})]
        }}),
        {cl_paragraphs}
"""

    # Build summary table rows
    summary_rows = ""
    for i, job in enumerate(top_jobs):
        score = job.get("score", 0)
        score_color = "2ECC71" if score >= 7 else "F39C12" if score >= 5 else "E74C3C"
        title = esc(job.get("title", ""))
        company = esc(job.get("company", ""))
        role_cat = esc(job.get("role_category", ""))

        summary_rows += f"""
        new TableRow({{
            children: [
                new TableCell({{
                    borders, width: {{ size: 500, type: WidthType.DXA }},
                    margins: cellMargins,
                    children: [new Paragraph({{ children: [new TextRun({{ text: "{i+1}", font: "Arial", size: 20 }})] }})]
                }}),
                new TableCell({{
                    borders, width: {{ size: 3200, type: WidthType.DXA }},
                    margins: cellMargins,
                    children: [new Paragraph({{ children: [new TextRun({{ text: `{title}`, font: "Arial", size: 20, bold: true }})] }})]
                }}),
                new TableCell({{
                    borders, width: {{ size: 2300, type: WidthType.DXA }},
                    margins: cellMargins,
                    children: [new Paragraph({{ children: [new TextRun({{ text: `{company}`, font: "Arial", size: 20 }})] }})]
                }}),
                new TableCell({{
                    borders, width: {{ size: 2000, type: WidthType.DXA }},
                    margins: cellMargins,
                    children: [new Paragraph({{ children: [new TextRun({{ text: `{role_cat}`, font: "Arial", size: 20 }})] }})]
                }}),
                new TableCell({{
                    borders, width: {{ size: 900, type: WidthType.DXA }},
                    margins: cellMargins,
                    shading: {{ fill: "{score_color}", type: ShadingType.CLEAR }},
                    children: [new Paragraph({{ alignment: AlignmentType.CENTER, children: [new TextRun({{ text: "{score}/10", font: "Arial", size: 20, bold: true, color: "FFFFFF" }})] }})]
                }}),
            ]
        }}),"""

    js_code = f"""
const fs = require("fs");
const {{ Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
         Header, Footer, AlignmentType, ExternalHyperlink,
         HeadingLevel, BorderStyle, WidthType, ShadingType,
         PageNumber, PageBreak }} = require("docx");

const border = {{ style: BorderStyle.SINGLE, size: 1, color: "DDDDDD" }};
const borders = {{ top: border, bottom: border, left: border, right: border }};
const cellMargins = {{ top: 60, bottom: 60, left: 100, right: 100 }};

const headerBorder = {{ style: BorderStyle.SINGLE, size: 1, color: "1A1A2E" }};
const headerBorders = {{ top: headerBorder, bottom: headerBorder, left: headerBorder, right: headerBorder }};

function headerCell(text, width) {{
    return new TableCell({{
        borders: headerBorders, width: {{ size: width, type: WidthType.DXA }},
        shading: {{ fill: "1A1A2E", type: ShadingType.CLEAR }},
        margins: cellMargins,
        children: [new Paragraph({{ children: [new TextRun({{ text, font: "Arial", size: 20, bold: true, color: "FFFFFF" }})] }})]
    }});
}}

const doc = new Document({{
    styles: {{
        default: {{ document: {{ run: {{ font: "Arial", size: 22 }} }} }},
    }},
    sections: [{{
        properties: {{
            page: {{
                size: {{ width: 11906, height: 16838 }},
                margin: {{ top: 1200, right: 1200, bottom: 1200, left: 1200 }}
            }}
        }},
        headers: {{
            default: new Header({{
                children: [new Paragraph({{
                    border: {{ bottom: {{ style: BorderStyle.SINGLE, size: 2, color: "E94560", space: 4 }} }},
                    children: [
                        new TextRun({{ text: "Daily Job Report", font: "Arial", size: 20, bold: true, color: "1A1A2E" }}),
                        new TextRun({{ text: "  |  {today}", font: "Arial", size: 18, color: "888888" }}),
                    ]
                }})]
            }})
        }},
        footers: {{
            default: new Footer({{
                children: [new Paragraph({{
                    alignment: AlignmentType.CENTER,
                    children: [
                        new TextRun({{ text: "Page ", font: "Arial", size: 18, color: "999999" }}),
                        new TextRun({{ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "999999" }}),
                    ]
                }})]
            }})
        }},
        children: [
            new Paragraph({{
                spacing: {{ after: 100 }},
                children: [new TextRun({{ text: "Daily Job Application Report", font: "Arial", size: 36, bold: true, color: "1A1A2E" }})]
            }}),
            new Paragraph({{
                spacing: {{ after: 60 }},
                children: [new TextRun({{ text: `{today}  |  {len(top_jobs)} jobs selected for review`, font: "Arial", size: 24, color: "666666" }})]
            }}),
            new Paragraph({{
                spacing: {{ after: 200 }},
                children: [new TextRun({{ text: "Each job below includes a direct link, fit analysis, and a tailored cover letter. Review, pick, and apply.", font: "Arial", size: 22, color: "444444" }})]
            }}),

            new Paragraph({{
                spacing: {{ before: 100, after: 120 }},
                children: [new TextRun({{ text: "Summary", font: "Arial", size: 28, bold: true, color: "1A1A2E" }})]
            }}),
            new Table({{
                width: {{ size: 8900, type: WidthType.DXA }},
                columnWidths: [500, 3200, 2300, 2000, 900],
                rows: [
                    new TableRow({{
                        children: [
                            headerCell("#", 500),
                            headerCell("Role", 3200),
                            headerCell("Company", 2300),
                            headerCell("Category", 2000),
                            headerCell("Score", 900),
                        ]
                    }}),
                    {summary_rows}
                ]
            }}),

            {job_sections}
        ]
    }}]
}});

Packer.toBuffer(doc).then(buffer => {{
    fs.writeFileSync(`{esc(output_path)}`, buffer);
    console.log("Done");
}});
"""

    js_file.write_text(js_code)
    result = subprocess.run(["node", str(js_file)], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        logging.error(f"DOCX generation failed: {result.stderr}")
        raise RuntimeError(f"DOCX generation failed: {result.stderr}")
    js_file.unlink()
    logging.info(f"📄 Report saved: {output_path}")


# ─────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────

async def run_pipeline(config: dict):
    logger = logging.getLogger("job_agent")
    logger.info("=" * 60)
    logger.info(f"🚀 Job Agent starting — {datetime.now().isoformat()}")
    logger.info("=" * 60)

    db = JobDatabase(config["paths"]["db_path"])
    run_id = db.start_run()
    resume_text = load_resume(config)

    output_dir = Path(config["paths"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    candidate = config["candidate"]
    preferences = config["preferences"]
    jobs_per_day = config["schedule"]["jobs_per_day"]

    # ── Step 1: Scrape ──
    # Auto-detect CI environment — skip slow browser scraping
    logger.info("📡 Step 1: Scraping job boards (all API-based)...")

    new_jobs = await scrape_all(
        roles=config["roles"],
        locations=config["locations"],
        excluded_companies=config.get("excluded_companies", []),
        excluded_title_keywords=config.get("excluded_title_keywords", []),
        excluded_locations=config.get("excluded_locations", []),
        greenhouse_boards=config.get("greenhouse_boards", []),
        lever_companies=config.get("lever_companies", []),
        adzuna_app_id=config.get("api_keys", {}).get("adzuna_app_id", "") or os.environ.get("ADZUNA_APP_ID", ""),
        adzuna_app_key=config.get("api_keys", {}).get("adzuna_app_key", "") or os.environ.get("ADZUNA_APP_KEY", ""),
        reed_api_key=config.get("api_keys", {}).get("reed", "") or os.environ.get("REED_API_KEY", ""),
    )
    discovered_count = 0

    for job in new_jobs:
        if not db.job_exists(job["external_id"]):
            db.insert_job(job)
            discovered_count += 1

    logger.info(f"📋 Discovered {discovered_count} new jobs (total scraped: {len(new_jobs)})")

    # ── Step 2: Score with Claude ──
    logger.info("🤖 Step 2: Scoring jobs with Claude...")

    unscored = db.get_top_unscored(limit=50)

    for job in unscored:
        if not job["description"]:
            db.update_status(job["external_id"], "skipped", error_message="No description")
            continue

        result = score_job(
            job_title=job["title"],
            job_company=job["company"],
            job_description=job["description"],
            resume_text=resume_text,
            preferences=preferences,
        )

        db.update_score(
            external_id=job["external_id"],
            score=result["score"],
            reasons=result["reasons"],
            concerns=result["concerns"],
        )

        db.update_status(
            job["external_id"],
            "scored",
            role_category=result.get("role_category", "other")
        )

        logger.info(f"  → {job['title']} @ {job['company']}: {result['score']}/10")

    # ── Step 4: Select top jobs (min score threshold) ──
    min_score = preferences.get("min_score", 7.5)
    logger.info(f"🏆 Step 4: Selecting top {jobs_per_day} jobs (min score: {min_score})...")

    top_jobs = db.get_top_scored_unapplied(limit=jobs_per_day * 3)  # Fetch more, then filter

    # Only keep jobs above the minimum score
    top_jobs = [j for j in top_jobs if (j.get("score") or 0) >= min_score]
    top_jobs = top_jobs[:jobs_per_day]  # Take the top N

    logger.info(f"  Found {len(top_jobs)} jobs scoring {min_score}+")
    if not top_jobs:
        logger.info("  ℹ️  No jobs met the minimum score threshold today. Try again tomorrow.")

    for job in top_jobs:
        logger.info(f"  → [{job['score']}] {job['title']} @ {job['company']} ({job.get('location', '')})")

    # ── Step 5: Generate cover letters ──
    if not top_jobs:
        logger.info("✍️  Step 5: Skipped — no jobs above minimum score today")
    else:
        logger.info("✍️  Step 5: Generating tailored cover letters...")

    for job in top_jobs:
        logger.info(f"  → {job['title']} @ {job['company']}")

        cover_letter = generate_cover_letter(
            job_title=job["title"],
            job_company=job["company"],
            job_description=job["description"],
            resume_text=resume_text,
            candidate_name=candidate["name"],
        )

        if cover_letter:
            db.update_status(job["external_id"], "ready", cover_letter=cover_letter)
            job["cover_letter"] = cover_letter
        else:
            job["cover_letter"] = "(Cover letter generation failed)"

    # ── Step 6: Generate DOCX ──
    date_str = datetime.now().strftime("%Y-%m-%d")
    docx_path = str(output_dir / f"job_report_{date_str}.docx")

    if top_jobs:
        logger.info("📄 Step 6: Generating Word document...")
        try:
            generate_report_docx(top_jobs, docx_path)
        except Exception as e:
            logger.error(f"DOCX generation failed: {e}")
    else:
        logger.info("📄 Step 6: Skipped — no jobs to report")
        docx_path = None

    # ── Step 7: Send email with ALL attachments ──
    logger.info("📧 Step 7: Sending email with report + cover letters + resume...")

    send_daily_report(
        jobs=top_jobs,
        total_discovered=discovered_count,
        config=config,
        attachment_path=docx_path if docx_path and Path(docx_path).exists() else None,
    )

    db.end_run(run_id, discovered_count, len(top_jobs), 0)

    logger.info("\n" + "=" * 60)
    logger.info(f"✅ Done — {len(top_jobs)} jobs in report, {discovered_count} new discovered")
    logger.info(f"📄 Report: {docx_path}")
    logger.info("=" * 60)

    db.close()


def main():
    config = load_config()
    setup_logging(config["paths"]["logs_dir"])
    asyncio.run(run_pipeline(config))


if __name__ == "__main__":
    main()
