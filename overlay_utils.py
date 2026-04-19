"""Shared OpenCV overlay drawing for camera capture and attendance sessions.

Keeps overlay styling in one place so capture and face attendance stay consistent.
"""

from __future__ import annotations

from datetime import datetime

import cv2
import numpy as np


def draw_camera_overlay(
    frame: np.ndarray,
    *,
    student_name: str,
    class_course: str,
    subject_name: str,
    status: str = "neutral",
    attendance_status: str | None = None,
    hint: str = "Press q to quit",
    extra_lines: list[str] | None = None,
) -> None:
    """Draw informational text on a BGR frame; updates time every call.

    status:
      - "match"  -> green text (recognized / present intent)
      - "no_match" -> red text (not recognized)
      - "neutral" -> cyan text (registration capture, etc.)
    """
    if status == "match":
        color = (0, 255, 0)  # BGR green
    elif status == "no_match":
        color = (0, 0, 255)  # BGR red
    else:
        color = (0, 255, 255)  # BGR yellow/cyan — high contrast on most scenes

    now = datetime.now().strftime("%H:%M:%S")
    lines = [
        f"Student: {student_name}",
        f"Class: {class_course}",
        f"Subject: {subject_name}",
        f"Time: {now}",
    ]
    if attendance_status:
        lines.append(f"Attendance: {attendance_status}")
    if extra_lines:
        lines.extend(extra_lines)

    y = 28
    for line in lines:
        cv2.putText(
            frame,
            line,
            (16, y),
            cv2.FONT_HERSHEY_DUPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )
        y += 30

    h = frame.shape[0]
    cv2.putText(
        frame,
        hint,
        (16, h - 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )