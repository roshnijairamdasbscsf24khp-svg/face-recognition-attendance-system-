"""Face recognition training and matching module."""

from __future__ import annotations

import pickle
import queue
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from attendance_manager import AttendanceManager
from config import DEFAULT_CAMERA_INDEX, RECOGNITION_THRESHOLD
from database import DatabaseManager
from overlay_utils import draw_camera_overlay
from student_registration import StudentRegistrationService
from utils import current_timestamp


class FaceRecognitionService:
    """Computes simple face embeddings and performs nearest-neighbor matching."""

    def __init__(self, db: DatabaseManager, dataset_dir: Path) -> None:
        self.db = db
        self.dataset_dir = dataset_dir
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def embedding_from_bgr_frame(frame: np.ndarray) -> np.ndarray:
        """Grayscale 64x64 flattened vector from full frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (64, 64))
        return resized.flatten().astype(np.float32) / 255.0

    @staticmethod
    def _compute_embedding(image_path: Path) -> np.ndarray | None:
        """Create embedding vector from a saved image file."""
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        resized = cv2.resize(img, (64, 64))
        return resized.flatten().astype(np.float32) / 255.0

    def train_student_encoding(self, student_id: int, student_code: str) -> bool:
        """Aggregate images for a student and store mean embedding."""
        student_dir = self.dataset_dir.resolve() / student_code
        images = list(student_dir.glob("*.jpg"))
        if not images:
            return False

        embeddings = []
        for p in images:
            emb = self._compute_embedding(p)
            if emb is not None:
                embeddings.append(emb)

        if not embeddings:
            return False

        mean_embedding = np.mean(embeddings, axis=0)
        payload = pickle.dumps(mean_embedding)

        self.db.execute(
            """
            INSERT INTO face_encodings (student_id, encoding, updated_at)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                encoding = VALUES(encoding),
                updated_at = VALUES(updated_at)
            """,
            (student_id, payload, current_timestamp()),
        )
        return True

    def match_embedding(self, probe_embedding: np.ndarray) -> int | None:
        """Return matching student_id when distance is below threshold."""
        rows = self.db.fetchall("SELECT student_id, encoding FROM face_encodings")
        if not rows:
            return None

        best_student_id = None
        best_distance = float("inf")
        for row in rows:
            candidate = pickle.loads(row["encoding"])
            distance = float(np.linalg.norm(probe_embedding - candidate))
            if distance < best_distance:
                best_distance = distance
                best_student_id = int(row["student_id"])

        if best_distance <= RECOGNITION_THRESHOLD:
            return best_student_id
        return None

    def run_live_face_attendance_session(
        self,
        attendance_manager: AttendanceManager,
        registration_service: StudentRegistrationService,
        subject_id: int,
        subject_name: str,
        class_course: str,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        *,
        frame_callback: Callable[[np.ndarray], None] | None = None,
        hidden_opencv_window: bool = False,
        key_queue: queue.Queue[int] | None = None,
    ) -> tuple[int | None, np.ndarray | None]:
        """
        Live webcam loop with dynamic overlay.
        Green overlay when a registered face matches; red when no match.
        Press SPACE to mark attendance; Q to exit without marking.
        Returns (student_id, last_frame) if marked, else (None, None).
        """
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1)
            if not cap.isOpened():
                raise RuntimeError("Unable to access camera device.")

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        last_frame: np.ndarray | None = None
        marked_student: int | None = None
        window_name = "Face Attendance — SPACE to mark | q to quit"
        hidden_setup = False
        use_hidden = hidden_opencv_window or (frame_callback is not None)

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                probe = self.embedding_from_bgr_frame(frame)
                matched_id = self.match_embedding(probe)

                if matched_id is not None:
                    row = registration_service.get_student(matched_id)
                    if row:
                        display_name = f"{row['first_name']} {row['last_name']}".strip()
                    else:
                        display_name = f"ID {matched_id}"
                    status = "match"
                    attendance_status = "RECOGNIZED — Press SPACE to mark PRESENT"
                else:
                    display_name = "Scanning…"
                    status = "no_match"
                    attendance_status = "SCANNING"

                draw_camera_overlay(
                    frame,
                    student_name=display_name,
                    class_course=class_course,
                    subject_name=subject_name,
                    status=status,
                    attendance_status=attendance_status,
                    hint="[SPACE] Mark Attendance | [Q] Quit",
                )

                if use_hidden:
                    if not hidden_setup:
                        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                        if key_queue is not None:
                            cv2.resizeWindow(window_name, 480, 320)
                            cv2.moveWindow(window_name, 48, 48)
                        else:
                            cv2.resizeWindow(window_name, 160, 120)
                            cv2.moveWindow(window_name, -4000, -4000)
                        hidden_setup = True
                    cv2.imshow(window_name, frame)
                else:
                    cv2.imshow(window_name, frame)

                if frame_callback is not None:
                    frame_callback(frame.copy())

                last_frame = frame.copy()

                key = cv2.waitKey(1) & 0xFF
                if key == 255:
                    key = 0

                if key_queue is not None:
                    gui_quit = False
                    gui_space = False
                    try:
                        while True:
                            gk = int(key_queue.get_nowait()) & 0xFF
                            if gk in (ord("q"), ord("Q")):
                                gui_quit = True
                            elif gk == 32:
                                gui_space = True
                    except queue.Empty:
                        pass
                    if gui_quit:
                        key = ord("q")
                    elif gui_space:
                        key = 32

                if key == ord("Q"):
                    key = ord("q")

                if key == ord("q"):
                    break

                if key == 32:
                    if matched_id is not None:
                        attendance_manager.mark_attendance(matched_id, subject_id)
                        marked_student = matched_id
                        break

        finally:
            cap.release()
            cv2.destroyAllWindows()

        return marked_student, last_frame