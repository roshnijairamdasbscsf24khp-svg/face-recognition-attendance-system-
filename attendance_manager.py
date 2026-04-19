"""Attendance service for marking and exporting records."""

from __future__ import annotations

import csv
from pathlib import Path

from database import DatabaseManager
from utils import current_timestamp, today_date


class AttendanceManager:
    """Business operations for attendance and enrollment lifecycle."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def mark_attendance(
        self, student_id: int, subject_id: int, attendance_date: str | None = None
    ) -> None:
        """Insert attendance entry for a student on a subject/date."""
        date_value = attendance_date or today_date()
        self.db.execute(
            """
            INSERT INTO attendance (student_id, subject_id, attendance_date, status, marked_at)
            VALUES (%s, %s, %s, 'present', %s)
            ON DUPLICATE KEY UPDATE
                status = VALUES(status),
                marked_at = VALUES(marked_at)
            """,
            (student_id, subject_id, date_value, current_timestamp()),
        )

    def update_attendance_status(
        self,
        student_id: int,
        subject_id: int,
        status: str,
        attendance_date: str | None = None,
    ) -> None:
        """Update status for existing attendance row."""
        date_value = attendance_date or today_date()
        self.db.execute(
            """
            UPDATE attendance
            SET status = %s, marked_at = %s
            WHERE student_id = %s AND subject_id = %s AND attendance_date = %s
            """,
            (status, current_timestamp(), student_id, subject_id, date_value),
        )

    def delete_attendance_record(self, attendance_id: int) -> None:
        """Delete attendance row by id."""
        self.db.execute("DELETE FROM attendance WHERE id = %s", (attendance_id,))

    def get_attendance_report(self, attendance_date: str | None = None) -> list[dict]:
        """Retrieve joined attendance list for dashboard/export."""
        date_value = attendance_date or today_date()
        rows = self.db.fetchall(
            """
            SELECT
                a.id,
                a.attendance_date,
                a.status,
                s.student_code,
                CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                sub.subject_code,
                sub.subject_name,
                a.marked_at
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            JOIN subjects sub ON sub.id = a.subject_id
            WHERE a.attendance_date = %s
            ORDER BY a.id DESC
            """,
            (date_value,),
        )
        return rows

    def export_csv(self, output_path: Path, attendance_date: str | None = None) -> Path:
        """Export attendance report to CSV and return written path."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report = self.get_attendance_report(attendance_date)

        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "id",
                    "attendance_date",
                    "status",
                    "student_code",
                    "student_name",
                    "subject_code",
                    "subject_name",
                    "marked_at",
                ],
            )
            writer.writeheader()
            writer.writerows(report)

        return output_path

    # ------------------------------------------------------------------
    # NEW METHOD 1 — View attendance by any date
    # Calls get_attendance_report() which already exists — zero risk.
    # ------------------------------------------------------------------
    def get_attendance_by_date(self, attendance_date: str) -> list[dict]:
        """Return attendance records for any given date (YYYY-MM-DD)."""
        return self.get_attendance_report(attendance_date)

    # ------------------------------------------------------------------
    # NEW METHOD 2 — Attendance percentage per student per subject
    # Pure SELECT query — reads only, touches nothing.
    # ------------------------------------------------------------------
    def get_attendance_percentage(self) -> list[dict]:
        """
        Return attendance percentage for every student per subject.
        Counts total class days (distinct dates with at least one attendance
        record) and how many of those each student was present.
        """
        rows = self.db.fetchall(
            """
            SELECT
                s.student_code,
                CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                sub.subject_code,
                sub.subject_name,
                COUNT(DISTINCT a.attendance_date) AS present_days,
                (
                    SELECT COUNT(DISTINCT attendance_date)
                    FROM attendance
                    WHERE subject_id = sub.id
                ) AS total_days,
                ROUND(
                    COUNT(DISTINCT a.attendance_date) * 100.0 /
                    NULLIF(
                        (
                            SELECT COUNT(DISTINCT attendance_date)
                            FROM attendance
                            WHERE subject_id = sub.id
                        ), 0
                    ), 1
                ) AS percentage
            FROM students s
            CROSS JOIN subjects sub
            LEFT JOIN attendance a
                ON a.student_id = s.id
                AND a.subject_id = sub.id
                AND a.status = 'present'
            GROUP BY s.id, s.student_code, s.first_name, s.last_name,
                     sub.id, sub.subject_code, sub.subject_name
            ORDER BY sub.subject_name, s.last_name, s.first_name
            """
        )
        return rows