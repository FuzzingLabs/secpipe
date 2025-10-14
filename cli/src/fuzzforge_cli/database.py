"""
Database module for FuzzForge CLI.

Handles SQLite database operations for local project management,
including runs, findings, and crash storage.
"""
# Copyright (c) 2025 FuzzingLabs
#
# Licensed under the Business Source License 1.1 (BSL). See the LICENSE file
# at the root of this repository for details.
#
# After the Change Date (four years from publication), this version of the
# Licensed Work will be made available under the Apache License, Version 2.0.
# See the LICENSE-APACHE file or http://www.apache.org/licenses/LICENSE-2.0
#
# Additional attribution and requirements are provided in the NOTICE file.


import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from contextlib import contextmanager

from pydantic import BaseModel
from .constants import DEFAULT_DB_TIMEOUT, DEFAULT_CLEANUP_DAYS, STATS_SAMPLE_SIZE

logger = logging.getLogger(__name__)


class RunRecord(BaseModel):
    """Database record for workflow runs"""
    run_id: str
    workflow: str
    status: str
    target_path: str
    parameters: Dict[str, Any] = {}
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class FindingRecord(BaseModel):
    """Database record for findings"""
    id: Optional[int] = None
    run_id: str
    sarif_data: Dict[str, Any]
    summary: Dict[str, Any] = {}
    created_at: datetime


class CrashRecord(BaseModel):
    """Database record for crash reports"""
    id: Optional[int] = None
    run_id: str
    crash_id: str
    signal: Optional[str] = None
    stack_trace: Optional[str] = None
    input_file: Optional[str] = None
    severity: str = "medium"
    timestamp: datetime


class FuzzForgeDatabase:
    """SQLite database manager for FuzzForge CLI projects"""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        workflow TEXT NOT NULL,
        status TEXT NOT NULL,
        target_path TEXT NOT NULL,
        parameters TEXT DEFAULT '{}',
        created_at TIMESTAMP NOT NULL,
        completed_at TIMESTAMP,
        metadata TEXT DEFAULT '{}'
    );

    CREATE TABLE IF NOT EXISTS findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        sarif_data TEXT NOT NULL,
        summary TEXT DEFAULT '{}',
        created_at TIMESTAMP NOT NULL,
        FOREIGN KEY (run_id) REFERENCES runs (run_id)
    );

    CREATE TABLE IF NOT EXISTS crashes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        crash_id TEXT NOT NULL,
        signal TEXT,
        stack_trace TEXT,
        input_file TEXT,
        severity TEXT DEFAULT 'medium',
        timestamp TIMESTAMP NOT NULL,
        FOREIGN KEY (run_id) REFERENCES runs (run_id)
    );

    CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status);
    CREATE INDEX IF NOT EXISTS idx_runs_workflow ON runs (workflow);
    CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at);
    CREATE INDEX IF NOT EXISTS idx_findings_run_id ON findings (run_id);
    CREATE INDEX IF NOT EXISTS idx_crashes_run_id ON crashes (run_id);
    """

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()

    def _initialize_db(self):
        """Initialize database with schema, handling corruption"""
        try:
            with self.connection() as conn:
                # Test database integrity first
                conn.execute("PRAGMA integrity_check").fetchone()
                conn.executescript(self.SCHEMA)
        except sqlite3.DatabaseError as e:
            logger.warning(f"Database corruption detected: {e}")
            # Backup corrupted database
            backup_path = self.db_path.with_suffix('.db.corrupted')
            if self.db_path.exists():
                self.db_path.rename(backup_path)
                logger.info(f"Corrupted database backed up to: {backup_path}")

            # Create fresh database
            with self.connection() as conn:
                conn.executescript(self.SCHEMA)
            logger.info("Created fresh database after corruption")

    @contextmanager
    def connection(self):
        """Context manager for database connections with proper resource management"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                timeout=DEFAULT_DB_TIMEOUT
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode=WAL")
            # Enable query optimization
            conn.execute("PRAGMA optimize")
            yield conn
            conn.commit()
        except sqlite3.OperationalError as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass  # Connection might be broken
            if "database is locked" in str(e).lower():
                raise sqlite3.OperationalError(
                    "Database is locked. Another FuzzForge process may be running."
                ) from e
            elif "database disk image is malformed" in str(e).lower():
                raise sqlite3.DatabaseError(
                    "Database is corrupted. Use 'ff init --force' to reset."
                ) from e
            raise
        except Exception:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass  # Connection might be broken
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass  # Ensure cleanup even if close fails

    # Run management methods

    def save_run(self, run: RunRecord) -> None:
        """Save or update a run record with validation"""
        try:
            # Validate JSON serialization before database write
            parameters_json = json.dumps(run.parameters)
            metadata_json = json.dumps(run.metadata)

            with self.connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO runs
                    (run_id, workflow, status, target_path, parameters, created_at, completed_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    run.run_id,
                    run.workflow,
                    run.status,
                    run.target_path,
                    parameters_json,
                    run.created_at,
                    run.completed_at,
                    metadata_json
                ))
        except (TypeError, ValueError) as e:
            raise ValueError(f"Failed to serialize run data: {e}") from e

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Get a run record by ID with error handling"""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,)
            ).fetchone()

            if row:
                try:
                    return RunRecord(
                        run_id=row["run_id"],
                        workflow=row["workflow"],
                        status=row["status"],
                        target_path=row["target_path"],
                        parameters=json.loads(row["parameters"] or "{}"),
                        created_at=row["created_at"],
                        completed_at=row["completed_at"],
                        metadata=json.loads(row["metadata"] or "{}")
                    )
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to deserialize run {run_id}: {e}")
                    # Return with empty dicts for corrupted JSON
                    return RunRecord(
                        run_id=row["run_id"],
                        workflow=row["workflow"],
                        status=row["status"],
                        target_path=row["target_path"],
                        parameters={},
                        created_at=row["created_at"],
                        completed_at=row["completed_at"],
                        metadata={}
                    )
            return None

    def list_runs(
        self,
        workflow: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[RunRecord]:
        """List runs with optional filters"""
        query = "SELECT * FROM runs WHERE 1=1"
        params = []

        if workflow:
            query += " AND workflow = ?"
            params.append(workflow)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            runs = []
            for row in rows:
                try:
                    runs.append(RunRecord(
                        run_id=row["run_id"],
                        workflow=row["workflow"],
                        status=row["status"],
                        target_path=row["target_path"],
                        parameters=json.loads(row["parameters"] or "{}"),
                        created_at=row["created_at"],
                        completed_at=row["completed_at"],
                        metadata=json.loads(row["metadata"] or "{}")
                    ))
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Skipping corrupted run {row['run_id']}: {e}")
                    # Skip corrupted records instead of failing
                    continue
            return runs

    def update_run_status(self, run_id: str, status: str, completed_at: Optional[datetime] = None):
        """Update run status"""
        with self.connection() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, completed_at = ? WHERE run_id = ?",
                (status, completed_at, run_id)
            )

    # Findings management methods

    def save_findings(self, finding: FindingRecord) -> int:
        """Save findings and return the ID"""
        with self.connection() as conn:
            cursor = conn.execute("""
                INSERT INTO findings (run_id, sarif_data, summary, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                finding.run_id,
                json.dumps(finding.sarif_data),
                json.dumps(finding.summary),
                finding.created_at
            ))
            return cursor.lastrowid

    def get_findings(self, run_id: str) -> Optional[FindingRecord]:
        """Get findings for a run"""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM findings WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
                (run_id,)
            ).fetchone()

            if row:
                return FindingRecord(
                    id=row["id"],
                    run_id=row["run_id"],
                    sarif_data=json.loads(row["sarif_data"]),
                    summary=json.loads(row["summary"]),
                    created_at=row["created_at"]
                )
            return None

    def list_findings(self, limit: int = 50) -> List[FindingRecord]:
        """List recent findings"""
        with self.connection() as conn:
            rows = conn.execute("""
                SELECT * FROM findings
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [
                FindingRecord(
                    id=row["id"],
                    run_id=row["run_id"],
                    sarif_data=json.loads(row["sarif_data"]),
                    summary=json.loads(row["summary"]),
                    created_at=row["created_at"]
                )
                for row in rows
            ]

    def get_all_findings(self,
                        workflow: Optional[str] = None,
                        severity: Optional[List[str]] = None,
                        since_date: Optional[datetime] = None,
                        limit: Optional[int] = None) -> List[FindingRecord]:
        """Get all findings with optional filters"""
        with self.connection() as conn:
            query = """
                SELECT f.*, r.workflow
                FROM findings f
                JOIN runs r ON f.run_id = r.run_id
                WHERE 1=1
            """
            params = []

            if workflow:
                query += " AND r.workflow = ?"
                params.append(workflow)

            if since_date:
                query += " AND f.created_at >= ?"
                params.append(since_date)

            query += " ORDER BY f.created_at DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            rows = conn.execute(query, params).fetchall()

            findings = []
            for row in rows:
                try:
                    finding = FindingRecord(
                        id=row["id"],
                        run_id=row["run_id"],
                        sarif_data=json.loads(row["sarif_data"]),
                        summary=json.loads(row["summary"]),
                        created_at=row["created_at"]
                    )

                    # Filter by severity if specified
                    if severity:
                        finding_severities = set()
                        if "runs" in finding.sarif_data:
                            for run in finding.sarif_data["runs"]:
                                for result in run.get("results", []):
                                    finding_severities.add(result.get("level", "note").lower())

                        if not any(sev.lower() in finding_severities for sev in severity):
                            continue

                    findings.append(finding)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Skipping malformed finding {row['id']}: {e}")
                    continue

            return findings

    def get_findings_by_workflow(self, workflow: str) -> List[FindingRecord]:
        """Get all findings for a specific workflow"""
        return self.get_all_findings(workflow=workflow)

    def get_aggregated_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics for all findings using SQL aggregation"""
        with self.connection() as conn:
            # Total findings and runs
            total_findings = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            total_runs = conn.execute("SELECT COUNT(DISTINCT run_id) FROM findings").fetchone()[0]

            # Findings by workflow
            workflow_stats = conn.execute("""
                SELECT r.workflow, COUNT(f.id) as count
                FROM findings f
                JOIN runs r ON f.run_id = r.run_id
                GROUP BY r.workflow
                ORDER BY count DESC
            """).fetchall()

            # Recent activity
            recent_findings = conn.execute("""
                SELECT COUNT(*) FROM findings
                WHERE created_at > datetime('now', '-7 days')
            """).fetchone()[0]

            # Use SQL JSON functions to aggregate severity stats efficiently
            # This avoids loading all findings into memory
            severity_stats = conn.execute("""
                SELECT
                    SUM(json_array_length(json_extract(sarif_data, '$.runs[0].results'))) as total_issues,
                    COUNT(*) as finding_count
                FROM findings
                WHERE json_extract(sarif_data, '$.runs[0].results') IS NOT NULL
            """).fetchone()

            total_issues = severity_stats["total_issues"] or 0

            # Get severity distribution using SQL
            # Note: This is a simplified version - for full accuracy we'd need JSON parsing
            # But it's much more efficient than loading all data into Python
            severity_counts = {"error": 0, "warning": 0, "note": 0, "info": 0}

            # Sample the first N findings for severity distribution
            # This gives a good approximation without loading everything
            sample_findings = conn.execute("""
                SELECT sarif_data
                FROM findings
                LIMIT ?
            """, (STATS_SAMPLE_SIZE,)).fetchall()

            for row in sample_findings:
                try:
                    data = json.loads(row["sarif_data"])
                    if "runs" in data:
                        for run in data["runs"]:
                            for result in run.get("results", []):
                                level = result.get("level", "note").lower()
                                severity_counts[level] = severity_counts.get(level, 0) + 1
                except (json.JSONDecodeError, KeyError):
                    continue

            # Extrapolate severity counts if we have more than sample size
            if total_findings > STATS_SAMPLE_SIZE:
                multiplier = total_findings / STATS_SAMPLE_SIZE
                for key in severity_counts:
                    severity_counts[key] = int(severity_counts[key] * multiplier)

            return {
                "total_findings_records": total_findings,
                "total_runs": total_runs,
                "total_issues": total_issues,
                "severity_distribution": severity_counts,
                "workflows": {row["workflow"]: row["count"] for row in workflow_stats},
                "recent_findings": recent_findings,
                "last_updated": datetime.now()
            }

    # Crash management methods

    def save_crash(self, crash: CrashRecord) -> int:
        """Save crash report and return the ID"""
        with self.connection() as conn:
            cursor = conn.execute("""
                INSERT INTO crashes
                (run_id, crash_id, signal, stack_trace, input_file, severity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                crash.run_id,
                crash.crash_id,
                crash.signal,
                crash.stack_trace,
                crash.input_file,
                crash.severity,
                crash.timestamp
            ))
            return cursor.lastrowid

    def get_crashes(self, run_id: str) -> List[CrashRecord]:
        """Get all crashes for a run"""
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM crashes WHERE run_id = ? ORDER BY timestamp DESC",
                (run_id,)
            ).fetchall()

            return [
                CrashRecord(
                    id=row["id"],
                    run_id=row["run_id"],
                    crash_id=row["crash_id"],
                    signal=row["signal"],
                    stack_trace=row["stack_trace"],
                    input_file=row["input_file"],
                    severity=row["severity"],
                    timestamp=row["timestamp"]
                )
                for row in rows
            ]

    # Utility methods

    def cleanup_old_runs(self, keep_days: int = DEFAULT_CLEANUP_DAYS) -> int:
        """Remove old runs and associated data"""
        cutoff_date = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - datetime.timedelta(days=keep_days)

        with self.connection() as conn:
            # Get run IDs to delete
            old_runs = conn.execute(
                "SELECT run_id FROM runs WHERE created_at < ?",
                (cutoff_date,)
            ).fetchall()

            if not old_runs:
                return 0

            run_ids = [row["run_id"] for row in old_runs]
            placeholders = ",".join("?" * len(run_ids))

            # Delete associated findings and crashes
            conn.execute(f"DELETE FROM findings WHERE run_id IN ({placeholders})", run_ids)
            conn.execute(f"DELETE FROM crashes WHERE run_id IN ({placeholders})", run_ids)

            # Delete runs
            conn.execute(f"DELETE FROM runs WHERE run_id IN ({placeholders})", run_ids)

            return len(run_ids)

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.connection() as conn:
            stats = {}

            # Run counts by status
            run_stats = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM runs
                GROUP BY status
            """).fetchall()
            stats["runs_by_status"] = {row["status"]: row["count"] for row in run_stats}

            # Total counts
            stats["total_runs"] = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            stats["total_findings"] = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            stats["total_crashes"] = conn.execute("SELECT COUNT(*) FROM crashes").fetchone()[0]

            # Recent activity
            stats["runs_last_7_days"] = conn.execute("""
                SELECT COUNT(*) FROM runs
                WHERE created_at > datetime('now', '-7 days')
            """).fetchone()[0]

            return stats

    def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        health = {
            "healthy": True,
            "issues": [],
            "recommendations": []
        }

        try:
            with self.connection() as conn:
                # Check database integrity
                integrity_result = conn.execute("PRAGMA integrity_check").fetchone()
                if integrity_result[0] != "ok":
                    health["healthy"] = False
                    health["issues"].append(f"Database integrity check failed: {integrity_result[0]}")

                # Check for orphaned records
                orphaned_findings = conn.execute("""
                    SELECT COUNT(*) FROM findings
                    WHERE run_id NOT IN (SELECT run_id FROM runs)
                """).fetchone()[0]

                if orphaned_findings > 0:
                    health["issues"].append(f"Found {orphaned_findings} orphaned findings")
                    health["recommendations"].append("Run database cleanup to remove orphaned records")

                orphaned_crashes = conn.execute("""
                    SELECT COUNT(*) FROM crashes
                    WHERE run_id NOT IN (SELECT run_id FROM runs)
                """).fetchone()[0]

                if orphaned_crashes > 0:
                    health["issues"].append(f"Found {orphaned_crashes} orphaned crashes")

                # Check database size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                if db_size > 100 * 1024 * 1024:  # 100MB
                    health["recommendations"].append("Database is large (>100MB). Consider cleanup.")

        except Exception as e:
            health["healthy"] = False
            health["issues"].append(f"Health check failed: {e}")

        return health


def get_project_db(project_dir: Optional[Path] = None) -> Optional[FuzzForgeDatabase]:
    """Get the database for the current project with error handling"""
    if project_dir is None:
        project_dir = Path.cwd()

    fuzzforge_dir = project_dir / ".fuzzforge"
    if not fuzzforge_dir.exists():
        return None

    db_path = fuzzforge_dir / "findings.db"
    try:
        return FuzzForgeDatabase(db_path)
    except Exception as e:
        logger.error(f"Failed to open project database: {e}")
        raise sqlite3.DatabaseError(f"Failed to open project database: {e}") from e


def ensure_project_db(project_dir: Optional[Path] = None) -> FuzzForgeDatabase:
    """Ensure project database exists, create if needed with error handling"""
    if project_dir is None:
        project_dir = Path.cwd()

    fuzzforge_dir = project_dir / ".fuzzforge"
    try:
        fuzzforge_dir.mkdir(exist_ok=True)
    except PermissionError as e:
        raise PermissionError(f"Cannot create .fuzzforge directory: {e}") from e

    db_path = fuzzforge_dir / "findings.db"
    try:
        return FuzzForgeDatabase(db_path)
    except Exception as e:
        logger.error(f"Failed to create/open project database: {e}")
        raise sqlite3.DatabaseError(f"Failed to create project database: {e}") from e