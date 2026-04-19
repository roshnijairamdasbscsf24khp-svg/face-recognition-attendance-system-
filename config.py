"""Centralized configuration for the Smart Attendance System."""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
DATASET_DIR = BASE_DIR / "dataset"
EXPORTS_DIR = BASE_DIR / "exports"
DATABASE_DIR = BASE_DIR / "database"

# MySQL connection settings
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "smart_attendance_system")

# Camera and recognition defaults
DEFAULT_CAMERA_INDEX = 0
CAPTURE_IMAGE_COUNT = 30

# RECOGNITION_THRESHOLD = 12.0 is the correct value for the 4096-dim
# pixel-vector L2 distance used in face_recognition_module.py.
# The original value of 0.60 was too tight and caused every probe to fail.
RECOGNITION_THRESHOLD = 12.0

# UI defaults
APP_TITLE = "Smart Attendance Management System"
WINDOW_SIZE = "1280x820"
UI_FONT_FAMILY = "Segoe UI"
DEFAULT_CLASS_COURSE = "BS-CS-4"
UI_BG_MAIN = "#ffffff"
UI_BG_PANEL = "#f1f5f9"
UI_ACCENT = "#2563eb"
UI_ACCENT_HOVER = "#1d4ed8"
UI_TEXT = "#0f172a"
UI_SIDEBAR_BG = "#0f172a"
UI_SIDEBAR_TEXT = "#e2e8f0"
UI_SIDEBAR_MUTED = "#94a3b8"
UI_SIDEBAR_ACTIVE = "#1e3a5f"
UI_HEADER_RULE = "#e2e8f0"
UI_CARD_BG = "#f1f5f9"
UI_CARD_BORDER = "#e2e8f0"
UI_SUCCESS = "#16a34a"
UI_SUCCESS_BG = "#dcfce7"