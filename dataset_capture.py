"""Capture and store face images for model enrollment."""

from __future__ import annotations

from pathlib import Path

import cv2

from config import CAPTURE_IMAGE_COUNT, DEFAULT_CAMERA_INDEX
from overlay_utils import draw_camera_overlay


class DatasetCaptureService:
    """Collects face samples from webcam and stores them on disk."""

    def __init__(self, dataset_dir: Path) -> None:
        self.dataset_dir = dataset_dir
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    def capture_student_faces(
        self,
        student_code: str,
        camera_index: int = DEFAULT_CAMERA_INDEX,
        sample_count: int = CAPTURE_IMAGE_COUNT,
        *,
        first_name: str = "",
        last_name: str = "",
        class_course: str = "",
        subject_name: str = "",
    ) -> int:
        """
        Capture face samples for a student.
        Returns number of saved frames.
        """
        display_name = f"{first_name} {last_name}".strip() or student_code

        # Use absolute path so cv2.imwrite never silently fails
        student_dir = self.dataset_dir.resolve() / student_code
        student_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            cap = cv2.VideoCapture(1)
            if not cap.isOpened():
                raise RuntimeError(
                    "Unable to access camera. Ensure a webcam is connected and not in use."
                )

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        saved = 0
        try:
            while saved < sample_count:
                ok, frame = cap.read()
                if not ok:
                    break

                draw_camera_overlay(
                    frame,
                    student_name=display_name,
                    class_course=class_course or "—",
                    subject_name=subject_name or "—",
                    status="neutral",
                    hint="Press q to quit early",
                    extra_lines=[f"Samples saved: {saved}/{sample_count}"],
                )
                cv2.imshow("Dataset Capture — Press q to quit", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

                image_path = student_dir / f"{student_code}_{saved:03d}.jpg"
                success = cv2.imwrite(str(image_path), frame)
                if success:
                    saved += 1
        finally:
            cap.release()
            cv2.destroyAllWindows()

        return saved