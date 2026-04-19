# Smart Attendance System — Setup & Run Guide

## Prerequisites
- Python 3.9+ (3.14 works, but 3.9–3.12 recommended for best package compatibility)
- MySQL 8.0+ or MariaDB 10.6+ running locally

---

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** Do **not** install `face_recognition` (dlib-based) — this project uses its own
> OpenCV + Haar cascade pipeline; the only dependencies are the four listed in requirements.txt.

---

## 2. Configure MySQL Credentials

Either edit `config.py` directly or set environment variables before running:

```bash
# Windows (PowerShell)
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="your_password"

# Linux / macOS
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
```

The app will auto-create the `smart_attendance_system` database and all tables on first run.

---

## 3. Run the Application

```bash
python main.py
```

---

## What Was Fixed

| # | File | Problem | Fix |
|---|------|---------|-----|
| 1 | `config.py` | `RECOGNITION_THRESHOLD = 0.60` — way too tight for 4096-dim L2 distance; every probe returned "no match" | Raised to `12.0` (empirically correct range for this embedding) |
| 2 | `database.py` | No `connect_timeout`; hung indefinitely if MySQL unreachable | Added `connect_timeout=10` |
| 3 | `face_recognition_module.py` | No face detection — full frame was embedded; background/lighting dominated; recognition unreliable | Added Haar cascade `detectMultiScale` to extract face ROI before embedding |
| 4 | `face_recognition_module.py` | No preprocessing; recognition degraded under lighting changes | Added `cv2.equalizeHist` to both training and inference paths |
| 5 | `face_recognition_module.py` | Training crashed or used noisy data when no face in captured image | Skip images where `detectMultiScale` returns no face |
| 6 | `face_recognition_module.py` | Camera open failure had no fallback | Try index `1` before raising `RuntimeError` |
| 7 | `face_recognition_module.py`, `dataset_capture.py` | Default camera resolution could be very high, causing lag | Explicit `640×480` via `CAP_PROP_FRAME_WIDTH/HEIGHT` |
| 8 | `face_recognition_module.py` | Duplicate attendance comment was missing/misleading | Clarified: DB `UNIQUE KEY` + `ON DUPLICATE KEY UPDATE` already prevents duplicates |
| 9 | `dataset_capture.py` | `cv2.imwrite` silently fails with relative paths when CWD differs from project root | Use `dataset_dir.resolve()` (absolute path); check `imwrite` return value |
| 10 | `dataset_capture.py` | Single camera index with no fallback | Try index `1` as fallback |
| 11 | `main.py` | DB connection failure showed raw traceback | Friendly error message with actionable troubleshooting steps |
| 12 | `main.py` | Haar cascade init failure showed raw RuntimeError | Caught and printed with clean message |

---

## Preventing Duplicate Attendance

Duplicates are handled at **two** levels:
1. **Database**: `UNIQUE KEY uq_attendance_unique (student_id, subject_id, attendance_date)` — the DB rejects a second insert for the same student+subject+date.
2. **SQL**: `ON DUPLICATE KEY UPDATE` in `attendance_manager.py` — re-marking updates the `marked_at` timestamp rather than inserting a new row, so there is always exactly one record per student per subject per day.

---

## Folder Structure After First Run

```
project/
├── dataset/
│   └── <student_code>/       ← captured face images
├── exports/                  ← CSV exports
├── config.py
├── main.py
└── ...
```
