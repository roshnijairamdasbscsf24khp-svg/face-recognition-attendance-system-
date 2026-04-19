"""MySQL database manager and schema bootstrap (PyMySQL driver)."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import Error as PyMySQLError


class DatabaseManager:
    """Handles MySQL connection lifecycle and schema initialization."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def _connect(self, *, database: str | None = None) -> pymysql.connections.Connection:
        """Open a connection with utf8mb4 (matches Workbench / modern MySQL defaults)."""
        kwargs: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "charset": "utf8mb4",
            "autocommit": False,
        }
        if database is not None:
            kwargs["database"] = database
        return pymysql.connect(**kwargs)

    @contextmanager
    def get_server_connection(self):
        """Yield a connection to the server without selecting a database."""
        conn = self._connect(database=None)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_connection(self):
        """Yield a connection scoped to the configured database."""
        conn = self._connect(database=self.database)
        try:
            yield conn
            conn.commit()
        except PyMySQLError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize_schema(self) -> None:
        """Create database and all required tables if missing."""
        with self.get_server_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            conn.commit()
            cur.close()

        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS students (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_code VARCHAR(64) UNIQUE NOT NULL,
                first_name VARCHAR(120) NOT NULL,
                last_name VARCHAR(120) NOT NULL,
                email VARCHAR(255),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NULL
            ) ENGINE=InnoDB
            """,
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id INT AUTO_INCREMENT PRIMARY KEY,
                subject_code VARCHAR(64) UNIQUE NOT NULL,
                subject_name VARCHAR(255) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NULL
            ) ENGINE=InnoDB
            """,
            """
            CREATE TABLE IF NOT EXISTS enrollments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                subject_id INT NOT NULL,
                enrolled_at DATETIME NOT NULL,
                UNIQUE KEY uq_student_subject (student_id, subject_id),
                CONSTRAINT fk_enrollment_student
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                CONSTRAINT fk_enrollment_subject
                    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            """,
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                subject_id INT NOT NULL,
                attendance_date DATE NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'present',
                marked_at DATETIME NOT NULL,
                UNIQUE KEY uq_attendance_unique (student_id, subject_id, attendance_date),
                CONSTRAINT fk_attendance_student
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                CONSTRAINT fk_attendance_subject
                    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            """,
            """
            CREATE TABLE IF NOT EXISTS face_encodings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL UNIQUE,
                encoding LONGBLOB NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT fk_face_encoding_student
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            ) ENGINE=InnoDB
            """,
        ]

        with self.get_connection() as conn:
            cur = conn.cursor()
            for ddl in ddl_statements:
                cur.execute(ddl)
            cur.close()

    def execute(
        self, query: str, params: tuple[Any, ...] | list[Any] = ()
    ) -> int:
        """Execute INSERT/UPDATE/DELETE and return last inserted id."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            last_id = int(cur.lastrowid or 0)
            cur.close()
            return last_id

    def fetchall(
        self, query: str, params: tuple[Any, ...] | list[Any] = ()
    ) -> list[dict]:
        """Fetch all records from SELECT query."""
        with self.get_connection() as conn:
            cur = conn.cursor(DictCursor)
            cur.execute(query, params)
            rows = cur.fetchall()
            cur.close()
            return list(rows)

    def fetchone(
        self, query: str, params: tuple[Any, ...] | list[Any] = ()
    ) -> dict | None:
        """Fetch single record from SELECT query."""
        with self.get_connection() as conn:
            cur = conn.cursor(DictCursor)
            cur.execute(query, params)
            row = cur.fetchone()
            cur.close()
            return row