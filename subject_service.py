"""Subject catalog seeding and lookup for attendance."""

from __future__ import annotations

from database import DatabaseManager
from utils import current_timestamp

# Fixed catalog: (subject_code, display_name) — seeded into MySQL; extend via DB later.
SUBJECT_CATALOG: list[tuple[str, str]] = [
    ("COA_PR", "Computer Organization and Assembly (Pr)"),
    ("TOA", "Theory of Automata"),
    ("ADBMS_PR", "Advance Database Management System (Pr)"),
    ("AI", "Artificial Intelligence"),
    ("COA", "Computer Organization and Assembly"),
    ("ADBMS", "Advance Database Management System"),
    ("AI_PR", "Artificial Intelligence (Pr)"),
    ("IS", "Information Security"),
    ("PAS", "Probability and Statistics"),
]


class SubjectService:
    """Ensures default subjects exist and exposes listing for the GUI."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def seed_catalog_if_needed(self) -> None:
        """Insert missing catalog rows (INSERT IGNORE keeps existing rows intact)."""
        ts = current_timestamp()
        for code, name in SUBJECT_CATALOG:
            self.db.execute(
                """
                INSERT IGNORE INTO subjects (subject_code, subject_name, created_at)
                VALUES (%s, %s, %s)
                """,
                (code, name, ts),
            )

    def list_subjects_ordered(self) -> list[dict]:
        """Return subjects in the same order as SUBJECT_CATALOG (dropdown order)."""
        codes = [c for c, _ in SUBJECT_CATALOG]
        placeholders = ", ".join(["%s"] * len(codes))
        return self.db.fetchall(
            f"""
            SELECT id, subject_code, subject_name
            FROM subjects
            ORDER BY FIELD(subject_code, {placeholders})
            """,
            tuple(codes),
        )

    def get_subject_by_id(self, subject_id: int) -> dict | None:
        """Lookup one subject by primary key."""
        return self.db.fetchone(
            "SELECT id, subject_code, subject_name FROM subjects WHERE id = %s",
            (subject_id,),
        )