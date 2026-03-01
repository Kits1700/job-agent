# 🚀 Deploy Job Agent to GitHub Actions (Free, Runs Daily at 8am)

## One-Time Setup (15 minutes)

### Step 1: Create a Private GitHub Repo

```bash
cd ~/Downloads/job-agent
git init
git branch -M main
```

Go to [github.com/new](https://github.com/new) → create a **private** repo called `job-agent`.

```bash
git remote add origin https://github.com/YOUR_USERNAME/job-agent.git
```

### Step 2: Add Your Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 5 secrets:

| Secret Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` (from console.anthropic.com) |
| `GMAIL_APP_PASSWORD` | Your 16-char Gmail app password |
| `EMAIL` | `saikeerthana.arun@gmail.com` |
| `PHONE` | `+44 7XXXXXXXXX` (your UK number) |
| `LINKEDIN_URL` | `https://www.linkedin.com/in/your-profile` |
| `RESUME_TEXT` | Paste your entire resume.txt content |

### Step 3: Add Your Resume PDF

Copy `resume.pdf` into the repo root. It will be committed with the code.

### Step 4: Push Everything

```bash
git add -A
git commit -m "Initial job agent setup"
git push -u origin main
```

### Step 5: Enable Actions

Go to your repo → **Actions** tab → Click **"I understand my workflows, go ahead and enable them"**

### Step 6: Test It!

Go to **Actions** → **Daily Job Agent** → **Run workflow** → Click the green button.

Watch it run. Within ~10 minutes you'll get an email with your top 5 jobs.

---

## How It Works

- **8:00 AM UK time every day** → GitHub spins up a fresh Linux server
- Installs Python, Node, Playwright, everything
- Runs your job agent (~5-10 minutes)
- Emails you the report with cover letters + resume attached
- Saves the report as a downloadable artifact in GitHub
- Commits `jobs.db` back to the repo so it remembers past jobs
- Server shuts down — you pay nothing

## FAQ

**Will I run out of free minutes?**
No. GitHub gives 2,000 minutes/month for private repos. Your agent uses ~10 min/day = ~300 min/month.

**What if I want to change the search queries or companies?**
Edit `.github/workflows/daily-jobs.yml` — the config is embedded right in the workflow. Push the change and it takes effect next run.

**Can I run it manually?**
Yes — Actions tab → Daily Job Agent → Run workflow.

**Where are the reports stored?**
1. Emailed to you (with attachments)
2. Downloadable from Actions → click a run → Artifacts section

**What about the database?**
`jobs.db` is committed back to the repo after each run. This means the agent remembers which jobs it's already seen and scored, so you never get duplicates.

**LinkedIn/Indeed scraping might be flaky on GitHub Actions?**
Yes — GitHub's IP ranges are sometimes blocked. The Greenhouse and Lever API scrapers are the most reliable. If LinkedIn/Indeed fail, the agent still runs and scores jobs from the API sources. Check the logs in Artifacts if you want to debug.
