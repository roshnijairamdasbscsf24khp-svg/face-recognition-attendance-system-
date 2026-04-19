"""Student registration service logic."""

from __future__ import annotations

from database import DatabaseManager
from utils import current_timestamp


class StudentRegistrationService:
    """Provides operations for onboarding and querying students."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def register_student(
        self, student_code: str, first_name: str, last_name: str, email: str = ""
    ) -> int:
        """Insert new student and return generated database ID."""
        student_id = self.db.execute(
            """
            INSERT INTO students (student_code, first_name, last_name, email, created_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (student_code, first_name, last_name, email, current_timestamp()),
        )
        return int(student_id)

    def get_student(self, student_id: int) -> dict | None:
        """Fetch single student by primary key."""
        return self.db.fetchone(
            """
            SELECT id, student_code, first_name, last_name, email, created_at, updated_at
            FROM students
            WHERE id = %s
            """,
            (student_id,),
        )

    def update_student(
        self,
        student_id: int,
        first_name: str,
        last_name: str,
        email: str = "",
    ) -> None:
        """Update editable student fields."""
        self.db.execute(
            """
            UPDATE students
            SET first_name = %s, last_name = %s, email = %s, updated_at = %s
            WHERE id = %s
            """,
            (first_name, last_name, email, current_timestamp(), student_id),
        )

    def delete_student(self, student_id: int) -> None:
        """Delete a student and cascaded dependent rows."""
        self.db.execute("DELETE FROM students WHERE id = %s", (student_id,))

    def list_students(self) -> list[dict]:
        """Return all registered students as dictionaries."""
        rows = self.db.fetchall(
            """
            SELECT id, student_code, first_name, last_name, email, created_at, updated_at
            FROM students
            ORDER BY id DESC
            """
        )
        return rows