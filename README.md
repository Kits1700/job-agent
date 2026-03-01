# 🎯 Automated Job Application Agent

An AI-powered job agent that finds, scores, and applies to the 10 most suitable jobs every day — fully automated.

## What It Does

Every day at your configured time, this agent:

1. **Scrapes** LinkedIn, Indeed, Greenhouse, and Lever for jobs matching your target roles (Human-AI, UX Research, Software Dev)
2. **Scores** each job 1-10 using Claude, comparing against your resume and preferences
3. **Picks the top 10** highest-scoring unapplied jobs
4. **Generates** a tailored cover letter for each using Claude
5. **Auto-submits** applications via API (Greenhouse/Lever) or browser automation (LinkedIn/Indeed)
6. **Emails you** a daily report with what was applied, what failed, and scores

## Quick Start

### 1. Install Dependencies

```bash
cd job-agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

Edit `config.yaml`:

- Fill in your **name, email, phone, LinkedIn URL**
- Set your **ANTHROPIC_API_KEY** (or export as env var)
- Set **email credentials** for daily reports (use Gmail App Password)
- Adjust **keywords, locations, salary preferences**
- Set your **daily run time**

### 3. Prepare Your Resume

You need two versions:
```bash
# 1. PDF resume for uploading to applications
cp /path/to/your/resume.pdf ./resume.pdf

# 2. Plain text resume for Claude to read
# Copy/paste your resume content into this file:
nano resume.txt
```

### 4. Run

```bash
# Run once immediately
python main.py

# OR run on a daily schedule
python scheduler.py

# OR use cron (recommended for production)
crontab -e
# Add: 0 8 * * * cd /path/to/job-agent && /usr/bin/python3 main.py >> /path/to/job-agent/logs/cron.log 2>&1
```

## Project Structure

```
job-agent/
├── config.yaml          # All configuration
├── main.py              # Orchestrator — runs the full pipeline
├── scheduler.py         # Daily scheduler (alternative to cron)
├── scrapers.py          # LinkedIn, Indeed, Greenhouse, Lever scrapers
├── ai_module.py         # Claude API: scoring, cover letters, resume tailoring
├── applicant.py         # Application submission (API + browser automation)
├── reporter.py          # Daily email reports
├── database.py          # SQLite database for tracking everything
├── requirements.txt     # Python dependencies
├── resume.pdf           # Your PDF resume (you provide this)
├── resume.txt           # Your plain text resume (you provide this)
├── jobs.db              # SQLite database (auto-created)
├── output/              # Generated cover letters
└── logs/                # Run logs
```

## Customization

### Add More Companies (Greenhouse/Lever)

Edit `scrapers.py` and add company board slugs:

```python
GREENHOUSE_BOARDS = [
    "anthropic",
    "your-target-company",  # ← add here
]

LEVER_COMPANIES = [
    "netflix",
    "your-target-company",  # ← add here
]
```

Find a company's board slug by looking at their careers page URL:
- `https://boards.greenhouse.io/stripe` → slug is `stripe`
- `https://jobs.lever.co/cloudflare` → slug is `cloudflare`

### Adjust Scoring

Edit the prompt in `ai_module.py` → `score_job()` to change how Claude evaluates fit.

### LinkedIn Login (for Easy Apply)

LinkedIn Easy Apply requires login. To enable:
1. Add credentials to `config.yaml` or env vars
2. Uncomment the LinkedIn Easy Apply path in `applicant.py`
3. ⚠️ Use with caution — LinkedIn may flag automated activity

### Email Setup (Gmail)

1. Enable 2-Factor Authentication on your Gmail
2. Go to https://myaccount.google.com/apppasswords
3. Generate an App Password
4. Use that as `sender_password` in config.yaml (NOT your real Gmail password)

## Cost Estimate

Claude API usage per daily run (10 applications):
- ~50 scoring calls × ~500 tokens = ~25K tokens
- ~10 cover letter calls × ~1000 tokens = ~10K tokens
- **Total: ~35K tokens/day ≈ $0.10-0.30/day** (using Sonnet)

## Important Notes

- **Rate limiting**: The agent adds delays between requests. Don't increase `jobs_per_day` too aggressively.
- **LinkedIn/Indeed scraping**: These sites may change their HTML structure. If scraping breaks, update the CSS selectors in `scrapers.py`.
- **Greenhouse/Lever APIs**: These are the most reliable application methods. Prioritize companies using these platforms.
- **Failed applications**: Check the daily email report. Jobs that fail auto-apply include a "Apply Manually" link.
- **Database**: All data is in `jobs.db`. You can query it with any SQLite tool to track your application history.

## Deploying to Run 24/7

### Option A: Your Own Machine (cron)
```bash
crontab -e
0 8 * * * cd /home/you/job-agent && python3 main.py
```

### Option B: Cloud VM (cheapest)
- AWS Lightsail ($3.50/mo) or DigitalOcean ($4/mo)
- Install Python, Playwright, set up cron

### Option C: GitHub Actions (free)
Create `.github/workflows/apply.yml`:
```yaml
name: Daily Job Applications
on:
  schedule:
    - cron: '0 8 * * *'
jobs:
  apply:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: playwright install chromium
      - run: python main.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```
