"""
Database module — tracks all discovered jobs, scores, and application status.
Uses SQLite so there's zero setup.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path


class JobDatabase:
    def __init__(self, db_path: str = "./jobs.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                url TEXT,
                source TEXT,
                description TEXT,
                salary TEXT,
                job_type TEXT,
                discovered_at TEXT DEFAULT (datetime('now')),
                score REAL,
                score_reasons TEXT,
                score_concerns TEXT,
                role_category TEXT,
                status TEXT DEFAULT 'discovered',
                applied_at TEXT,
                cover_letter TEXT,
                tailored_resume_path TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS daily_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT,
                jobs_discovered INTEGER DEFAULT 0,
                jobs_applied INTEGER DEFAULT 0,
                jobs_failed INTEGER DEFAULT 0,
                started_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT,
                report_sent INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    def job_exists(self, external_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM jobs WHERE external_id = ?", (external_id,)
        ).fetchone()
        return row is not None

    def insert_job(self, job: dict) -> int:
        cur = self.conn.execute("""
            INSERT OR IGNORE INTO jobs
                (external_id, title, company, location, url, source, description,
                 salary, job_type, role_category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job.get("external_id"),
            job.get("title"),
            job.get("company"),
            job.get("location"),
            job.get("url"),
            job.get("source"),
            job.get("description"),
            job.get("salary"),
            job.get("job_type"),
            job.get("role_category"),
        ))
        self.conn.commit()
        return cur.lastrowid

    def update_score(self, external_id: str, score: float, reasons: str, concerns: str):
        self.conn.execute("""
            UPDATE jobs SET score = ?, score_reasons = ?, score_concerns = ?
            WHERE external_id = ?
        """, (score, reasons, concerns, external_id))
        self.conn.commit()

    def update_status(self, external_id: str, status: str, **kwargs):
        sets = ["status = ?"]
        vals = [status]
        if status == "applied":
            sets.append("applied_at = ?")
            vals.append(datetime.utcnow().isoformat())
        for k, v in kwargs.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        vals.append(external_id)
        self.conn.execute(
            f"UPDATE jobs SET {', '.join(sets)} WHERE external_id = ?", vals
        )
        self.conn.commit()

    def get_top_unscored(self, limit=50) -> list[dict]:
        rows = self.conn.execute("""
            SELECT * FROM jobs WHERE score IS NULL AND status = 'discovered'
            ORDER BY discovered_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_top_scored_unapplied(self, limit=10) -> list[dict]:
        rows = self.conn.execute("""
            SELECT * FROM jobs
            WHERE score IS NOT NULL AND status = 'scored'
            ORDER BY score DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_todays_applications(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT * FROM jobs
            WHERE DATE(applied_at) = DATE('now')
            ORDER BY score DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def get_all_applied(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT * FROM jobs WHERE status = 'applied'
            ORDER BY applied_at DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def start_run(self) -> int:
        cur = self.conn.execute(
            "INSERT INTO daily_runs (run_date) VALUES (?)",
            (datetime.utcnow().strftime("%Y-%m-%d"),)
        )
        self.conn.commit()
        return cur.lastrowid

    def end_run(self, run_id: int, discovered: int, applied: int, failed: int):
        self.conn.execute("""
            UPDATE daily_runs SET
                jobs_discovered = ?, jobs_applied = ?, jobs_failed = ?,
                completed_at = datetime('now')
            WHERE id = ?
        """, (discovered, applied, failed, run_id))
        self.conn.commit()

    def close(self):
        self.conn.close()
