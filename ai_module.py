"""
Claude AI module — job scoring, cover letter generation, resume tailoring.
Tuned for: UX Researcher, Human-AI Researcher, AI UX Designer,
           Responsible AI Researcher, Product Researcher
"""
import json
import logging
import os

import anthropic

logger = logging.getLogger("job_agent.ai")

MODEL = "claude-sonnet-4-20250514"


def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set.")
    return anthropic.Anthropic(api_key=api_key)


# ─────────────────────────────────────────────────
# 1. SCORE & RANK JOBS
# ─────────────────────────────────────────────────

def score_job(
    job_title: str,
    job_company: str,
    job_description: str,
    resume_text: str,
    preferences: dict,
) -> dict:
    """Score a job 1-10 for fit against the candidate's profile."""
    client = get_client()

    prompt = f"""You are a career advisor scoring job fit for a specific candidate.

## Candidate Profile
{resume_text}

## What the candidate is looking for (in priority order):
1. **UX Researcher** — Usability testing, mixed methods, ethnography, user interviews. This is the broadest and most hireable category.
2. **Human-AI Interaction Researcher** — Roles focused on how humans interact with AI systems, trust calibration, explainability, human-in-the-loop design.
3. **AI UX Designer / Researcher** — Hybrid roles at AI companies combining research and design for AI products.
4. **Responsible AI / AI Ethics Researcher** — Trust, safety, fairness, governance, explainability in AI systems.
5. **Product Researcher** — User research that informs product decisions at tech companies.

## What the candidate does NOT want:
- ML Engineer, Data Scientist, Data Analyst, Data Engineer roles
- Pure software engineering without UX/HCI/AI research connection
- AI Trainer, Data Labeler, Annotation, Content Moderator, Prompt Rater roles
- DevOps, Cloud, Infrastructure, Security, QA roles
- Sales, Marketing, Recruitment roles

## Candidate preferences:
- Locations: UK and EU (remote OK)
- Minimum salary: {preferences.get('min_salary', 'flexible')} {preferences.get('currency', 'GBP')}
- Experience level: {', '.join(preferences.get('experience_level', ['entry', 'junior', 'mid', 'graduate']))}

## Job to evaluate:
- Title: {job_title}
- Company: {job_company}
- Description:
{job_description[:4000]}

## Scoring rules (BE STRICT — candidate only applies to 5 jobs/day with full intention):
- 9-10: Exceptional match. Title is one of the 5 target roles. Requirements closely match experience. Company is reputable. Location is UK, EU, or Bengaluru.
- 8-8.9: Strong match. Clear alignment with one of the target roles. Most requirements met. Would be worth a carefully crafted application.
- 7-7.9: Good match. Relevant role with meaningful overlap. Some stretch but candidate could make a strong case.
- 5-6.9: Partial match. Related field but not core target, or major gaps in requirements, or wrong seniority level (too senior/too junior).
- 3-4.9: Weak match. Tangentially related. Not worth an intentional application.
- 1-2.9: Not relevant at all.

## CRITICAL — BE STRICT:
- This candidate applies to ONLY 5 jobs per day with FULL intention. Every recommendation must be worth their time.
- Score DOWN any role that is primarily ML engineering, data science, data analysis, backend dev, or pure software dev even if it mentions "AI"
- Score DOWN roles requiring 5+ years experience (candidate has ~2 years professional + MSc)
- Score DOWN US-based roles — candidate can only work in UK, EU, or Bengaluru India
- Score UP roles that explicitly mention: user research, HCI, human-AI interaction, explainable AI, trust, usability, mixed methods
- Score UP roles at AI companies that need someone who understands the human side
- A generic "UX Researcher" at a good company = 7.5-8
- A "Human-AI Researcher" at an AI company = 8.5-9.5
- A "Senior Staff UX Researcher" requiring 8+ years = 4-5 (too senior)

Respond ONLY with valid JSON (no markdown fences):
{{
    "score": <float 1-10>,
    "reasons": "<2-3 sentences on why this is/isn't a good fit>",
    "concerns": "<1-2 sentences on gaps or risks>",
    "role_category": "<one of: ux-researcher, human-ai-researcher, ai-ux-designer, responsible-ai, product-researcher, other>"
}}
"""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse score response: {e}")
        return {"score": 0, "reasons": "Parse error", "concerns": str(e), "role_category": "other"}
    except Exception as e:
        logger.error(f"Scoring error: {e}")
        return {"score": 0, "reasons": "API error", "concerns": str(e), "role_category": "other"}


# ─────────────────────────────────────────────────
# 2. GENERATE COVER LETTER
# ─────────────────────────────────────────────────

def generate_cover_letter(
    job_title: str,
    job_company: str,
    job_description: str,
    resume_text: str,
    candidate_name: str,
) -> str:
    """Generate a tailored cover letter."""
    client = get_client()

    prompt = f"""Write a cover letter that shows GENUINE passion and intentionality for this specific role.

## About Me
Name: {candidate_name}
{resume_text}

## Job Details
- Title: {job_title}
- Company: {job_company}
- Description:
{job_description[:4000]}

## CRITICAL INSTRUCTIONS — READ CAREFULLY:

**TONE:** This is NOT a generic "I'm writing to express my interest" cover letter. Write like someone who has been waiting for THIS exact role. Show fire, drive, and specificity. The reader should feel "this person really wants THIS job, not just any job."

**STRUCTURE:**
1. Open with a hook — why THIS company and THIS role specifically excites you. Reference something specific about the company's work, mission, or a recent project. No generic openers.
2. Show don't tell — connect 2-3 specific experiences from my background to specific requirements in their job description. Use concrete numbers and outcomes (e.g. "improved engagement by 40%", "study with n=40 participants").
3. Show intellectual curiosity — mention what I'd be excited to explore or build in this role. Show I've thought about the problems they're solving.
4. Close with confidence and a clear call to action.

**KEY EXPERIENCES TO DRAW FROM (pick the most relevant):**
- MSc thesis: Designed explainable AI interfaces to reduce overreliance in Human-LLM interaction (University of Nottingham, Distinction)
- IISc SPIRE Lab: Led human-AI interaction design for an AI language learning tool used by 100+ users. Designed human-in-the-loop feedback mechanisms. Improved learner engagement by ~40%.
- LLM Friction Study: Mixed-methods study (n=40) showing task-specific friction increased cognitive engagement and calibrated trust without harming UX. Built custom React + GPT-4o research platform.
- Qualcomm: Engineering credibility — Python/C++ automation, CI/CD, cross-functional collaboration at scale.
- Certifications: Google UX Design, Meta Front-End Developer

**VISA/SPONSORSHIP:**
- I have the right to work in the UK (no sponsorship needed for UK roles)
- For EU roles (Germany, Netherlands, Ireland, France, Sweden, Switzerland, etc.): Add a brief, confident note near the end: "I would require visa sponsorship for this role and am happy to discuss the process further."
- For Bengaluru/India roles: I am an Indian citizen, no sponsorship needed — do NOT mention sponsorship
- Determine the location from the job details and handle accordingly

**RULES:**
- 280-350 words
- No clichés: "I'm excited to apply", "I believe I would be a great fit", "Dear Hiring Manager"
- Start with "Dear {job_company} team,"
- Write in first person, conversational but professional
- Every sentence should earn its place — no filler
- Output ONLY the cover letter text, nothing else
"""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Cover letter generation error: {e}")
        return ""


# ─────────────────────────────────────────────────
# 3. TAILOR RESUME SUMMARY
# ─────────────────────────────────────────────────

def tailor_resume_summary(
    job_title: str,
    job_description: str,
    resume_text: str,
) -> str:
    """Generate a tailored professional summary for the top of a resume."""
    client = get_client()

    prompt = f"""Based on my resume and the target job, write a tailored professional summary
(3-4 sentences) I can put at the top of my resume for this application.

## My Resume
{resume_text}

## Target Job
- Title: {job_title}
- Description:
{job_description[:3000]}

## Instructions
- Highlight skills and experiences most relevant to THIS job
- Use strong, specific language
- Keep it under 80 words
- Output ONLY the summary text
"""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Resume tailoring error: {e}")
        return ""
