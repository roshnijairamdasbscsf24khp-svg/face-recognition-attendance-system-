"""Tkinter GUI — university-style attendance dashboard (layout/styling only; services unchanged)."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any

import cv2
import numpy as np

from attendance_manager import AttendanceManager
from config import (
    APP_TITLE,
    DEFAULT_CLASS_COURSE,
    EXPORTS_DIR,
    UI_ACCENT,
    UI_ACCENT_HOVER,
    UI_BG_MAIN,
    UI_BG_PANEL,
    UI_CARD_BG,
    UI_CARD_BORDER,
    UI_FONT_FAMILY,
    UI_HEADER_RULE,
    UI_SIDEBAR_ACTIVE,
    UI_SIDEBAR_BG,
    UI_SIDEBAR_MUTED,
    UI_SIDEBAR_TEXT,
    UI_SUCCESS,
    UI_SUCCESS_BG,
    UI_TEXT,
    WINDOW_SIZE,
)
from dataset_capture import DatasetCaptureService
from face_recognition_module import FaceRecognitionService
from student_registration import StudentRegistrationService
from subject_service import SubjectService
from utils import today_date


def _style_flat_button(
    button: tk.Button,
    *,
    bg: str,
    hover_bg: str,
) -> None:
    def on_enter(_event: object) -> None:
        button.configure(bg=hover_bg)

    def on_leave(_event: object) -> None:
        button.configure(bg=bg)

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)


class SmartAttendanceGUI:
    """Main desktop interface with sidebar navigation, dashboard cards, and live panels."""

    _DEPT_LINE = "Department of Computer Science"
    _PROGRAM_LINE = "BS-CS Semester 4"

    def __init__(
        self,
        registration_service: StudentRegistrationService,
        attendance_manager: AttendanceManager,
        dataset_service: DatasetCaptureService,
        face_service: FaceRecognitionService,
        subject_service: SubjectService,
    ) -> None:
        self.registration_service = registration_service
        self.attendance_manager = attendance_manager
        self.dataset_service = dataset_service
        self.face_service = face_service
        self.subject_service = subject_service

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.configure(bg=UI_BG_MAIN)
        self.root.minsize(1024, 680)

        self._thumb_image: Any = None
        self._live_cam_image: Any = None
        self._subject_rows: list[dict] = []
        self._face_session_lock = threading.Lock()
        self._face_session_running = False
        self._face_key_queue: queue.Queue[int] | None = None
        self._face_key_capture = False
        self._face_hotkey_tokens: list[tuple[tk.Misc, str, str]] = []

        self._apply_global_ttk_style()
        self._build_layout()
        self._tick_clock()
        self._refresh_dashboard_stats()
        self._reload_attendance_log_table()

        # Bring window to front
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(1000, lambda: self.root.attributes("-topmost", False))

    def _apply_global_ttk_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TCombobox", fieldbackground="white", background="white")
        style.configure(
            "Treeview",
            font=(UI_FONT_FAMILY, 10),
            rowheight=26,
            background="white",
            fieldbackground="white",
        )
        style.configure("Treeview.Heading", font=(UI_FONT_FAMILY, 10, "bold"))
        style.map("Treeview", background=[("selected", UI_ACCENT)])

    def _font(self, size: int, weight: str = "normal") -> tuple[str, int, str]:
        return (UI_FONT_FAMILY, size, weight) if weight != "normal" else (UI_FONT_FAMILY, size)

    def _build_layout(self) -> None:
        outer = tk.Frame(self.root, bg=UI_BG_MAIN)
        outer.pack(fill="both", expand=True)

        sidebar = tk.Frame(outer, bg=UI_SIDEBAR_BG, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        main = tk.Frame(outer, bg=UI_BG_MAIN)
        main.pack(side="left", fill="both", expand=True, padx=(0, 0))

        self._build_sidebar(sidebar)
        self._build_main(main)

        status_frame = tk.Frame(self.root, bg=UI_BG_PANEL, height=36)
        status_frame.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar(value="Ready — select a subject, then choose an action.")
        tk.Label(
            status_frame,
            textvariable=self.status_var,
            anchor="w",
            font=self._font(10),
            bg=UI_BG_PANEL,
            fg=UI_TEXT,
            padx=16,
            pady=10,
        ).pack(fill="x")

    def _sidebar_btn(self, parent: tk.Widget, text: str, command: Any) -> tk.Button:
        b = tk.Button(
            parent,
            text=text,
            command=command,
            font=self._font(11),
            fg=UI_SIDEBAR_TEXT,
            bg=UI_SIDEBAR_BG,
            activebackground=UI_SIDEBAR_ACTIVE,
            activeforeground=UI_SIDEBAR_TEXT,
            relief=tk.FLAT,
            bd=0,
            anchor="w",
            padx=20,
            pady=14,
            cursor="hand2",
        )
        b.pack(fill="x", padx=8, pady=2)

        def on_enter(_e: object) -> None:
            if b.cget("state") != "disabled":
                b.configure(bg=UI_SIDEBAR_ACTIVE)

        def on_leave(_e: object) -> None:
            b.configure(bg=UI_SIDEBAR_BG)

        b.bind("<Enter>", on_enter)
        b.bind("<Leave>", on_leave)
        return b

    def _build_sidebar(self, sidebar: tk.Frame) -> None:
        tk.Label(
            sidebar,
            text="Menu",
            font=self._font(10, "bold"),
            fg=UI_SIDEBAR_MUTED,
            bg=UI_SIDEBAR_BG,
        ).pack(anchor="w", padx=24, pady=(24, 8))

        self._sidebar_btn(sidebar, "  Dashboard", self._on_dashboard)
        self._sidebar_btn(sidebar, "  Register Student", self.register_student)
        self._sidebar_btn(sidebar, "  View Students", self.view_students)
        self._sidebar_btn(sidebar, "  Mark Attendance", self.mark_attendance)
        self._sidebar_btn(sidebar, "  Export Reports", self.export_attendance_csv)
        self._sidebar_btn(sidebar, "  View by Date", self.view_attendance_by_date)
        self._sidebar_btn(sidebar, "  Attendance %", self.view_attendance_percentage)
        self._sidebar_btn(sidebar, "  Quit", self.root.destroy)

        tk.Frame(sidebar, bg=UI_SIDEBAR_BG, height=8).pack(fill="x")

    def _build_main(self, main: tk.Frame) -> None:
        pad = {"padx": 24, "pady": 12}
        header = tk.Frame(main, bg=UI_BG_MAIN)
        header.pack(fill="x", **pad)

        cards = tk.Frame(main, bg=UI_BG_MAIN)
        cards.pack(fill="x", padx=24, pady=(0, 8))
        self._build_summary_cards(cards)

        controls = tk.Frame(main, bg=UI_BG_MAIN)
        controls.pack(fill="x", padx=24, pady=(4, 12))

        tk.Label(
            controls,
            text="Subject",
            font=self._font(10, "bold"),
            bg=UI_BG_MAIN,
            fg=UI_TEXT,
        ).grid(row=0, column=0, sticky="w")

        self._subject_rows = self.subject_service.list_subjects_ordered()
        subject_names = [r["subject_name"] for r in self._subject_rows]

        self.subject_var = tk.StringVar(value=subject_names[0] if subject_names else "")
        self.subject_combo = ttk.Combobox(
            controls,
            textvariable=self.subject_var,
            values=subject_names,
            state="readonly" if subject_names else "disabled",
            font=(UI_FONT_FAMILY, 10),
            width=48,
        )
        self.subject_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.subject_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_subject_changed())
        controls.grid_columnconfigure(0, weight=1)

        btn_kw = dict(
            font=self._font(10, "bold"),
            fg="white",
            activeforeground="white",
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
        )
        manual_btn = tk.Button(
            controls,
            text="Mark Manual",
            command=self.mark_attendance,
            bg=UI_ACCENT,
            activebackground=UI_ACCENT_HOVER,
            **btn_kw,
        )
        face_btn = tk.Button(
            controls,
            text="Mark Face",
            command=self.mark_attendance_face,
            bg=UI_ACCENT,
            activebackground=UI_ACCENT_HOVER,
            **btn_kw,
        )
        manual_btn.grid(row=1, column=1, padx=(16, 8), sticky="e")
        face_btn.grid(row=1, column=2, padx=(0, 0), sticky="e")
        for b in (manual_btn, face_btn):
            _style_flat_button(b, bg=UI_ACCENT, hover_bg=UI_ACCENT_HOVER)

        self._build_header(header)

        mid = tk.Frame(main, bg=UI_BG_MAIN)
        mid.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        mid.grid_columnconfigure(0, weight=2)
        mid.grid_columnconfigure(1, weight=3)
        mid.grid_rowconfigure(0, weight=1)

        left_mid = tk.Frame(mid, bg=UI_BG_MAIN)
        left_mid.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right_mid = tk.Frame(mid, bg=UI_BG_MAIN)
        right_mid.grid(row=0, column=1, sticky="nsew")

        self._build_recognition_panel(left_mid)
        self._build_camera_panel(right_mid)

        table_wrap = tk.Frame(main, bg=UI_BG_MAIN)
        table_wrap.pack(fill="both", expand=False, padx=24, pady=(0, 16))
        self._build_attendance_table(table_wrap)

    def _build_header(self, header: tk.Frame) -> None:
        left = tk.Frame(header, bg=UI_BG_MAIN)
        left.pack(side="left", fill="x", expand=True)

        tk.Label(
            left,
            text=APP_TITLE,
            font=self._font(18, "bold"),
            fg=UI_TEXT,
            bg=UI_BG_MAIN,
        ).pack(anchor="w")
        tk.Label(
            left,
            text=self._DEPT_LINE,
            font=self._font(11),
            fg="#475569",
            bg=UI_BG_MAIN,
        ).pack(anchor="w", pady=(2, 0))
        tk.Label(
            left,
            text=self._PROGRAM_LINE,
            font=self._font(11),
            fg="#475569",
            bg=UI_BG_MAIN,
        ).pack(anchor="w")

        tk.Frame(header, bg=UI_HEADER_RULE, height=1).pack(fill="x", pady=(12, 0))

        meta = tk.Frame(header, bg=UI_BG_MAIN)
        meta.pack(fill="x", pady=(12, 0))

        right = tk.Frame(meta, bg=UI_BG_MAIN)
        right.pack(side="right")

        self.header_date_var = tk.StringVar()
        self.header_time_var = tk.StringVar()
        self.header_subject_var = tk.StringVar()

        tk.Label(
            right,
            textvariable=self.header_date_var,
            font=self._font(10),
            fg="#64748b",
            bg=UI_BG_MAIN,
        ).pack(anchor="e")
        tk.Label(
            right,
            textvariable=self.header_time_var,
            font=self._font(12, "bold"),
            fg=UI_TEXT,
            bg=UI_BG_MAIN,
        ).pack(anchor="e", pady=(2, 0))
        tk.Label(
            right,
            textvariable=self.header_subject_var,
            font=self._font(10),
            fg=UI_ACCENT,
            bg=UI_BG_MAIN,
        ).pack(anchor="e", pady=(4, 0))

        self._sync_header_subject_line()

    def _sync_header_subject_line(self) -> None:
        name = self.subject_var.get().strip() if hasattr(self, "subject_var") else ""
        self.header_subject_var.set(f"Selected subject: {name}" if name else "Selected subject: —")

    def _build_summary_cards(self, parent: tk.Frame) -> None:
        self.card_total_var = tk.StringVar(value="0")
        self.card_present_var = tk.StringVar(value="0")
        self.card_absent_var = tk.StringVar(value="0")
        self.card_subject_var = tk.StringVar(value="—")

        specs = [
            ("Total Students", self.card_total_var),
            ("Present Today", self.card_present_var),
            ("Absent Today", self.card_absent_var),
            ("Selected Subject", self.card_subject_var),
        ]

        for i, (title, var) in enumerate(specs):
            card = tk.Frame(
                parent,
                bg=UI_CARD_BG,
                highlightbackground=UI_CARD_BORDER,
                highlightthickness=1,
            )
            card.grid(row=0, column=i, padx=(0 if i == 0 else 10, 0), sticky="nsew")
            parent.grid_columnconfigure(i, weight=1)

            tk.Label(
                card,
                text=title,
                font=self._font(9),
                fg="#64748b",
                bg=UI_CARD_BG,
            ).pack(anchor="w", padx=16, pady=(14, 4))
            tk.Label(
                card,
                textvariable=var,
                font=self._font(16, "bold"),
                fg=UI_TEXT,
                bg=UI_CARD_BG,
                wraplength=200,
                justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 14))

    def _build_recognition_panel(self, parent: tk.Frame) -> None:
        wrap = tk.Frame(
            parent,
            bg=UI_BG_PANEL,
            highlightbackground=UI_CARD_BORDER,
            highlightthickness=1,
        )
        wrap.pack(fill="both", expand=True)

        tk.Label(
            wrap,
            text="Last Attendance Marked",
            font=self._font(11, "bold"),
            fg=UI_TEXT,
            bg=UI_BG_PANEL,
        ).pack(anchor="w", padx=16, pady=(14, 8))

        self.rec_name_var = tk.StringVar(value="—")
        self.rec_class_var = tk.StringVar(value=DEFAULT_CLASS_COURSE)
        self.rec_subject_var = tk.StringVar(value="—")
        self.rec_time_var = tk.StringVar(value="—")

        info = tk.Frame(wrap, bg=UI_BG_PANEL)
        info.pack(fill="x", padx=16, pady=(0, 8))

        def row(label: str, var: tk.StringVar) -> None:
            tk.Label(
                info,
                text=label,
                font=self._font(9),
                fg="#64748b",
                bg=UI_BG_PANEL,
                width=12,
                anchor="w",
            ).pack(anchor="w")
            tk.Label(
                info,
                textvariable=var,
                font=self._font(11, "bold"),
                fg=UI_TEXT,
                bg=UI_BG_PANEL,
                anchor="w",
            ).pack(anchor="w", pady=(0, 6))

        row("Student", self.rec_name_var)
        row("Class", self.rec_class_var)
        row("Subject", self.rec_subject_var)
        row("Time", self.rec_time_var)

        badge_row = tk.Frame(wrap, bg=UI_BG_PANEL)
        badge_row.pack(fill="x", padx=16, pady=(4, 16))
        tk.Label(badge_row, text="Status", font=self._font(9), fg="#64748b", bg=UI_BG_PANEL).pack(
            anchor="w"
        )
        self.rec_status_badge = tk.Label(
            badge_row,
            text="—",
            font=self._font(10, "bold"),
            fg=UI_SUCCESS,
            bg=UI_SUCCESS_BG,
            padx=12,
            pady=6,
        )
        self.rec_status_badge.pack(anchor="w", pady=(4, 0))

    def _build_camera_panel(self, parent: tk.Frame) -> None:
        wrap = tk.Frame(
            parent,
            bg="#0f172a",
            highlightbackground=UI_CARD_BORDER,
            highlightthickness=1,
        )
        wrap.pack(fill="both", expand=True)

        tk.Label(
            wrap,
            text="Live camera preview",
            font=self._font(11, "bold"),
            fg="#e2e8f0",
            bg="#0f172a",
        ).pack(anchor="w", padx=12, pady=(10, 6))

        self.camera_label = tk.Label(
            wrap,
            text="Camera idle — start Face Attendance to stream here.",
            font=self._font(10),
            fg="#94a3b8",
            bg="#1e293b",
            width=52,
            height=22,
            justify="center",
            wraplength=520,
            takefocus=True,
            highlightthickness=2,
            highlightbackground="#334155",
            highlightcolor=UI_ACCENT,
        )
        self.camera_label.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_attendance_table(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="Live attendance log (today)",
            font=self._font(11, "bold"),
            fg=UI_TEXT,
            bg=UI_BG_MAIN,
        ).pack(anchor="w", pady=(0, 8))

        frame = tk.Frame(parent, bg=UI_BG_MAIN)
        frame.pack(fill="both", expand=True)

        scroll = ttk.Scrollbar(frame)
        scroll.pack(side="right", fill="y")

        self.attendance_tree = ttk.Treeview(
            frame,
            columns=("student", "subject", "time", "status"),
            show="headings",
            yscrollcommand=scroll.set,
            height=7,
        )
        scroll.config(command=self.attendance_tree.yview)

        self.attendance_tree.heading("student", text="Student Name")
        self.attendance_tree.heading("subject", text="Subject")
        self.attendance_tree.heading("time", text="Time")
        self.attendance_tree.heading("status", text="Status")

        self.attendance_tree.column("student", width=260, anchor="w")
        self.attendance_tree.column("subject", width=320, anchor="w")
        self.attendance_tree.column("time", width=120, anchor="center")
        self.attendance_tree.column("status", width=100, anchor="center")

        self.attendance_tree.pack(side="left", fill="both", expand=True)

    def _tick_clock(self) -> None:
        self.header_date_var.set(datetime.now().strftime("%A, %d %B %Y"))
        self.header_time_var.set(datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def _on_dashboard(self) -> None:
        self._refresh_dashboard_stats()
        self._reload_attendance_log_table()
        self._set_status("Dashboard refreshed.")

    def _on_subject_changed(self) -> None:
        self._sync_header_subject_line()
        self._refresh_dashboard_stats()

    def _refresh_dashboard_stats(self) -> None:
        students = self.registration_service.list_students()
        total = len(students)
        report = self.attendance_manager.get_attendance_report()
        present_rows = [r for r in report if str(r.get("status", "")).lower() == "present"]
        codes_present = {r.get("student_code") for r in present_rows if r.get("student_code")}
        distinct_present = len(codes_present)
        absent = max(0, total - distinct_present)

        self.card_total_var.set(str(total))
        self.card_present_var.set(str(distinct_present))
        self.card_absent_var.set(str(absent))
        subj = self.subject_var.get().strip() if hasattr(self, "subject_var") else ""
        self.card_subject_var.set(subj if subj else "—")

    def _reload_attendance_log_table(self) -> None:
        for iid in self.attendance_tree.get_children():
            self.attendance_tree.delete(iid)
        rows = self.attendance_manager.get_attendance_report()
        for r in rows:
            name = str(r.get("student_name") or "").strip()
            subj = str(r.get("subject_name") or "").strip()
            marked = r.get("marked_at")
            if hasattr(marked, "strftime"):
                t_disp = marked.strftime("%H:%M:%S")
            elif isinstance(marked, str) and len(marked) >= 19:
                t_disp = marked[11:19]
            else:
                t_disp = (str(marked or "")[-8:] if marked else "") or "—"
            st = str(r.get("status") or "").upper()
            self.attendance_tree.insert("", "end", values=(name, subj, t_disp, st))

    def _update_recognition_panel(
        self,
        *,
        name: str,
        subject_name: str,
        time_str: str,
        status_label: str,
        status_is_present: bool,
    ) -> None:
        self.rec_name_var.set(name)
        self.rec_class_var.set(DEFAULT_CLASS_COURSE)
        self.rec_subject_var.set(subject_name)
        self.rec_time_var.set(time_str)
        self.rec_status_badge.configure(text=status_label)
        if status_is_present:
            self.rec_status_badge.configure(fg=UI_SUCCESS, bg=UI_SUCCESS_BG)
        else:
            self.rec_status_badge.configure(fg="#64748b", bg="#e2e8f0")

    def _update_live_camera_preview(self, frame_bgr: np.ndarray) -> None:
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self.camera_label.configure(
                text="Install Pillow for live preview:\npip install pillow",
                image="",
            )
            return

        h, w = frame_bgr.shape[:2]
        max_w, max_h = 640, 420
        scale = min(max_w / w, max_h / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(frame_bgr, (nw, nh))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb)
        self._live_cam_image = ImageTk.PhotoImage(image=pil_image)
        self.camera_label.configure(image=self._live_cam_image, text="")

    def _reset_camera_panel(self) -> None:
        self._live_cam_image = None
        self.camera_label.configure(
            image="",
            text="Camera idle — start Face Attendance to stream here.",
        )

    def _face_bind_hotkeys(self) -> None:
        self._face_hotkey_tokens.clear()
        for widget in (self.root, self.camera_label):
            bid = widget.bind("<Key>", self._on_face_hotkey_key, add="+")
            self._face_hotkey_tokens.append((widget, "<Key>", bid))
        for widget in (self.root, self.camera_label):
            sp = widget.bind("<KeyPress-space>", self._on_face_hotkey_space_only, add="+")
            self._face_hotkey_tokens.append((widget, "<KeyPress-space>", sp))
            for qseq in ("<KeyPress-q>", "<KeyPress-Q>"):
                qb = widget.bind(qseq, self._on_face_hotkey_q_only, add="+")
                self._face_hotkey_tokens.append((widget, qseq, qb))

    def _face_unbind_hotkeys(self) -> None:
        for widget, seq, bid in self._face_hotkey_tokens:
            try:
                widget.unbind(seq, bid)
            except tk.TclError:
                pass
        self._face_hotkey_tokens.clear()

    def _on_face_hotkey_key(self, event: tk.Event) -> str | None:
        if not self._face_key_capture or self._face_key_queue is None:
            return None
        ks = event.keysym or ""
        ch = event.char or ""
        if ks in ("space", "Space") or ch == " ":
            self._face_key_queue.put(32)
            return "break"
        if ks in ("q", "Q"):
            self._face_key_queue.put(ord("q"))
            return "break"
        return None

    def _on_face_hotkey_space_only(self, event: tk.Event) -> str | None:
        if not self._face_key_capture or self._face_key_queue is None:
            return None
        self._face_key_queue.put(32)
        return "break"

    def _on_face_hotkey_q_only(self, event: tk.Event) -> str | None:
        if not self._face_key_capture or self._face_key_queue is None:
            return None
        self._face_key_queue.put(ord("q"))
        return "break"

    def _get_selected_subject(self) -> tuple[int, str] | None:
        if not self._subject_rows:
            messagebox.showerror("Subjects", "No subjects found. Check database seeding.")
            return None
        name = self.subject_var.get().strip()
        for row in self._subject_rows:
            if row["subject_name"] == name:
                return int(row["id"]), str(row["subject_name"])
        messagebox.showwarning("Subject", "Please select a subject from the dropdown.")
        return None

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
        self.root.update_idletasks()

    def _show_face_thumbnail(self, frame_bgr: np.ndarray | None) -> None:
        if frame_bgr is None:
            return
        self._update_live_camera_preview(frame_bgr)

    def register_student(self) -> None:
        picked = self._get_selected_subject()
        if not picked:
            return
        _, subject_name = picked

        student_code = simpledialog.askstring("Student Code", "Enter student code:")
        first_name = simpledialog.askstring("First Name", "Enter first name:")
        last_name = simpledialog.askstring("Last Name", "Enter last name:")
        email = simpledialog.askstring("Email", "Enter email (optional):") or ""

        if not (student_code and first_name and last_name):
            messagebox.showwarning("Missing Data", "Student code and names are required.")
            return

        try:
            student_id = self.registration_service.register_student(
                student_code=student_code.strip(),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
                email=email.strip(),
            )
            self._set_status(f"Registered student ID {student_id} — starting face capture…")

            try:
                captured = self.dataset_service.capture_student_faces(
                    student_code.strip(),
                    first_name=first_name.strip(),
                    last_name=last_name.strip(),
                    class_course=DEFAULT_CLASS_COURSE,
                    subject_name=subject_name,
                )
                if captured > 0:
                    self.face_service.train_student_encoding(student_id, student_code.strip())
                    self._set_status(
                        f"Student {student_id}: {captured} samples saved; encoding trained."
                    )
                    messagebox.showinfo(
                        "Success",
                        f"Student registered (ID {student_id}). {captured} face images captured.",
                    )
                else:
                    self._set_status(f"Student {student_id} saved — no face images captured.")
                    messagebox.showwarning(
                        "Warning",
                        "Student registered but no face images were captured.",
                    )
            except Exception as exc:
                self._set_status(f"Student {student_id} saved — face capture failed.")
                messagebox.showerror("Face Capture Failed", str(exc))
            self._refresh_dashboard_stats()
        except Exception as exc:
            messagebox.showerror("Registration Failed", str(exc))

    def view_students(self) -> None:
        students = self.registration_service.list_students()
        if not students:
            messagebox.showinfo("Students", "No students found.")
            return

        lines = [
            f"{s['id']} | {s['student_code']} | {s['first_name']} {s['last_name']}"
            for s in students
        ]
        messagebox.showinfo("Registered Students", "\n".join(lines))

    def mark_attendance_face(self) -> None:
        with self._face_session_lock:
            if self._face_session_running:
                self._set_status("Face attendance session already running.")
                return
            self._face_session_running = True

        picked = self._get_selected_subject()
        if not picked:
            with self._face_session_lock:
                self._face_session_running = False
            return
        subject_id, subject_name = picked

        self._set_status(
            f"Face attendance — {subject_name}. "
            "Click the app window, then [SPACE] to mark or [Q] to quit."
        )

        self._face_key_queue = queue.Queue()
        self._face_key_capture = True
        self._face_bind_hotkeys()
        self.root.focus_force()
        self.camera_label.focus_set()

        def worker() -> None:
            err: Exception | None = None
            student_id: int | None = None
            last_frame: np.ndarray | None = None
            try:
                _preview_tick = [0]

                def on_frame(frame_copy: np.ndarray) -> None:
                    _preview_tick[0] += 1
                    if _preview_tick[0] % 2 != 0:
                        return
                    snap = frame_copy.copy()
                    self.root.after(0, lambda fc=snap: self._update_live_camera_preview(fc))

                student_id, last_frame = self.face_service.run_live_face_attendance_session(
                    self.attendance_manager,
                    self.registration_service,
                    subject_id=subject_id,
                    subject_name=subject_name,
                    class_course=DEFAULT_CLASS_COURSE,
                    frame_callback=on_frame,
                    key_queue=self._face_key_queue,
                )
            except Exception as exc:
                err = exc

            def finish() -> None:
                self._face_unbind_hotkeys()
                self._face_key_capture = False
                self._face_key_queue = None
                with self._face_session_lock:
                    self._face_session_running = False
                if err is not None:
                    messagebox.showerror("Face Attendance Error", str(err))
                    self._set_status("Face attendance aborted due to an error.")
                    self._reset_camera_panel()
                    return
                if student_id is None:
                    self._set_status("Face attendance closed — no attendance marked.")
                    self._reset_camera_panel()
                    return

                stu = self.registration_service.get_student(student_id)
                label = (
                    f"{stu['first_name']} {stu['last_name']}".strip()
                    if stu
                    else f"ID {student_id}"
                )
                ts = datetime.now().strftime("%I:%M %p")
                ts_log = datetime.now().strftime("%H:%M:%S")
                self._set_status(
                    f"Attendance marked for {label} at {ts_log} — {subject_name}."
                )
                messagebox.showinfo(
                    "Attendance",
                    f"Attendance marked for {label} ({subject_name}).",
                )
                self._update_recognition_panel(
                    name=label,
                    subject_name=subject_name,
                    time_str=ts,
                    status_label="PRESENT ✓",
                    status_is_present=True,
                )
                self._reload_attendance_log_table()
                self._refresh_dashboard_stats()
                self._show_face_thumbnail(last_frame)
                self.root.after(3500, self._reset_camera_panel)

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def mark_attendance(self) -> None:
        picked = self._get_selected_subject()
        if not picked:
            return
        subject_id, subject_name = picked

        student_id = simpledialog.askinteger("Student ID", "Enter student ID:")
        if student_id is None:
            return

        try:
            self.attendance_manager.mark_attendance(student_id, subject_id)
            ts = datetime.now().strftime("%H:%M:%S")
            ts_panel = datetime.now().strftime("%I:%M %p")
            stu = self.registration_service.get_student(student_id)
            label = (
                f"{stu['first_name']} {stu['last_name']}".strip()
                if stu
                else str(student_id)
            )
            self._set_status(
                f"Attendance marked for {label} at {ts} — {subject_name} (manual)."
            )
            messagebox.showinfo("Success", "Attendance marked successfully.")
            self._update_recognition_panel(
                name=label,
                subject_name=subject_name,
                time_str=ts_panel,
                status_label="PRESENT ✓",
                status_is_present=True,
            )
            self._reload_attendance_log_table()
            self._refresh_dashboard_stats()
        except Exception as exc:
            messagebox.showerror("Attendance Failed", str(exc))

    def export_attendance_csv(self) -> None:
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        default_name = f"attendance_{today_date()}.csv"
        path_str = filedialog.asksaveasfilename(
            title="Export attendance CSV",
            defaultextension=".csv",
            initialfile=default_name,
            initialdir=str(EXPORTS_DIR),
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path_str:
            self._set_status("Export cancelled.")
            return

        out = Path(path_str)
        try:
            self.attendance_manager.export_csv(out)
            self._set_status(f"Exported attendance to {out}")
            messagebox.showinfo("Export", f"Saved:\n{out}")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    # ------------------------------------------------------------------
    # NEW FEATURE 1 — View attendance by any date
    # Opens a popup window with a date entry and a table.
    # Does NOT touch any existing method.
    # ------------------------------------------------------------------
    def view_attendance_by_date(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Attendance by Date")
        win.geometry("860x520")
        win.configure(bg=UI_BG_MAIN)
        win.grab_set()

        top = tk.Frame(win, bg=UI_BG_MAIN)
        top.pack(fill="x", padx=20, pady=14)

        tk.Label(
            top,
            text="Attendance by Date",
            font=self._font(14, "bold"),
            bg=UI_BG_MAIN,
            fg=UI_TEXT,
        ).pack(side="left")

        right = tk.Frame(top, bg=UI_BG_MAIN)
        right.pack(side="right")

        tk.Label(
            right,
            text="Date (YYYY-MM-DD):",
            font=self._font(10),
            bg=UI_BG_MAIN,
            fg=UI_TEXT,
        ).pack(side="left", padx=(0, 6))

        date_var = tk.StringVar(value=today_date())
        date_entry = tk.Entry(
            right,
            textvariable=date_var,
            font=self._font(10),
            width=14,
            relief=tk.SOLID,
            bd=1,
        )
        date_entry.pack(side="left", padx=(0, 8))

        # Table frame
        table_frame = tk.Frame(win, bg=UI_BG_MAIN)
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        scroll = ttk.Scrollbar(table_frame)
        scroll.pack(side="right", fill="y")

        tree = ttk.Treeview(
            table_frame,
            columns=("code", "name", "subject", "status", "time"),
            show="headings",
            yscrollcommand=scroll.set,
            height=16,
        )
        scroll.config(command=tree.yview)
        tree.heading("code", text="Student Code")
        tree.heading("name", text="Student Name")
        tree.heading("subject", text="Subject")
        tree.heading("status", text="Status")
        tree.heading("time", text="Marked At")
        tree.column("code", width=110, anchor="w")
        tree.column("name", width=200, anchor="w")
        tree.column("subject", width=280, anchor="w")
        tree.column("status", width=90, anchor="center")
        tree.column("time", width=110, anchor="center")
        tree.pack(side="left", fill="both", expand=True)

        status_lbl = tk.Label(
            win,
            text="",
            font=self._font(9),
            bg=UI_BG_MAIN,
            fg="#64748b",
        )
        status_lbl.pack(pady=(0, 8))

        def load() -> None:
            date_str = date_var.get().strip()
            if len(date_str) != 10 or date_str[4] != "-" or date_str[7] != "-":
                messagebox.showwarning(
                    "Invalid Date",
                    "Please enter date in YYYY-MM-DD format.",
                    parent=win,
                )
                return
            for iid in tree.get_children():
                tree.delete(iid)
            try:
                rows = self.attendance_manager.get_attendance_by_date(date_str)
                for r in rows:
                    marked = r.get("marked_at")
                    if hasattr(marked, "strftime"):
                        t = marked.strftime("%H:%M:%S")
                    elif isinstance(marked, str) and len(marked) >= 19:
                        t = marked[11:19]
                    else:
                        t = str(marked or "")[-8:] or "—"
                    tree.insert(
                        "",
                        "end",
                        values=(
                            r.get("student_code", ""),
                            r.get("student_name", ""),
                            r.get("subject_name", ""),
                            str(r.get("status", "")).upper(),
                            t,
                        ),
                    )
                count = len(rows)
                status_lbl.config(
                    text=f"{count} record{'s' if count != 1 else ''} found for {date_str}"
                )
            except Exception as exc:
                messagebox.showerror("Error", str(exc), parent=win)

        tk.Button(
            right,
            text="Load",
            command=load,
            font=self._font(10, "bold"),
            bg=UI_ACCENT,
            fg="white",
            activebackground=UI_ACCENT_HOVER,
            activeforeground="white",
            relief=tk.FLAT,
            padx=14,
            pady=4,
            cursor="hand2",
        ).pack(side="left")

        # Load today automatically on open
        load()

    # ------------------------------------------------------------------
    # NEW FEATURE 2 — Attendance percentage per student per subject
    # Opens a popup with a table showing % for each student/subject combo.
    # Does NOT touch any existing method.
    # ------------------------------------------------------------------
    def view_attendance_percentage(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("Attendance Percentage Report")
        win.geometry("860x520")
        win.configure(bg=UI_BG_MAIN)
        win.grab_set()

        tk.Label(
            win,
            text="Attendance Percentage — All Students",
            font=self._font(14, "bold"),
            bg=UI_BG_MAIN,
            fg=UI_TEXT,
        ).pack(anchor="w", padx=20, pady=(14, 10))

        table_frame = tk.Frame(win, bg=UI_BG_MAIN)
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        scroll = ttk.Scrollbar(table_frame)
        scroll.pack(side="right", fill="y")

        tree = ttk.Treeview(
            table_frame,
            columns=("code", "name", "subject", "present", "total", "pct"),
            show="headings",
            yscrollcommand=scroll.set,
            height=16,
        )
        scroll.config(command=tree.yview)
        tree.heading("code",    text="Student Code")
        tree.heading("name",    text="Student Name")
        tree.heading("subject", text="Subject")
        tree.heading("present", text="Present Days")
        tree.heading("total",   text="Total Days")
        tree.heading("pct",     text="Attendance %")
        tree.column("code",    width=110, anchor="w")
        tree.column("name",    width=200, anchor="w")
        tree.column("subject", width=280, anchor="w")
        tree.column("present", width=100, anchor="center")
        tree.column("total",   width=90,  anchor="center")
        tree.column("pct",     width=110, anchor="center")
        tree.pack(side="left", fill="both", expand=True)

        # Color-code rows: red < 75%, green >= 75%
        tree.tag_configure("low",  foreground="#dc2626")
        tree.tag_configure("good", foreground="#16a34a")

        status_lbl = tk.Label(
            win,
            text="",
            font=self._font(9),
            bg=UI_BG_MAIN,
            fg="#64748b",
        )
        status_lbl.pack(pady=(0, 8))

        try:
            rows = self.attendance_manager.get_attendance_percentage()
            for r in rows:
                pct = r.get("percentage") or 0
                present = r.get("present_days", 0)
                total = r.get("total_days", 0)
                tag = "good" if pct >= 75 else "low"
                tree.insert(
                    "",
                    "end",
                    values=(
                        r.get("student_code", ""),
                        r.get("student_name", ""),
                        r.get("subject_name", ""),
                        present,
                        total,
                        f"{pct}%",
                    ),
                    tags=(tag,),
                )
            status_lbl.config(
                text=f"{len(rows)} records  |  Green = 75%+ attendance  |  Red = below 75%"
            )
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=win)

    def run(self) -> None:
        self.root.mainloop()