"""Application entrypoint for Smart Attendance System."""

from attendance_manager import AttendanceManager
from config import (
    DATASET_DIR,
    EXPORTS_DIR,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)
from database import DatabaseManager
from dataset_capture import DatasetCaptureService
from face_recognition_module import FaceRecognitionService
from gui import SmartAttendanceGUI
from student_registration import StudentRegistrationService
from subject_service import SubjectService
from utils import ensure_directories


def bootstrap() -> DatabaseManager:
    """Prepare required directories and initialize MySQL schema."""
    ensure_directories([DATASET_DIR, EXPORTS_DIR])
    db = DatabaseManager(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
    )
    db.initialize_schema()
    return db


def main() -> None:
    """Create services and launch desktop UI."""
    db = bootstrap()
    subject_service = SubjectService(db)
    subject_service.seed_catalog_if_needed()

    registration_service = StudentRegistrationService(db)
    attendance_service = AttendanceManager(db)
    dataset_service = DatasetCaptureService(DATASET_DIR)
    face_service = FaceRecognitionService(db, DATASET_DIR)

    app = SmartAttendanceGUI(
        registration_service,
        attendance_service,
        dataset_service,
        face_service,
        subject_service,
    )
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()