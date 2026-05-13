"""Club Manager — simple desktop app for tracking yearly memberships.

Run directly with ``python main.py`` or build a single .exe with
``build.ps1`` (uses PyInstaller).
"""
from __future__ import annotations

import os
import re
import sys
import threading
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import messagebox, simpledialog, ttk
from typing import Optional

import autorun
import db
import i18n
import mailer
from db import Member
from i18n import t
from mailer import EmailSettings


AUTO_SEND_INTERVAL_MS = 30 * 60 * 1000  # check every 30 minutes
LOG_FILENAME = "clubmanager.log"

# Hourly + half-hourly time presets used in the Automation combo box.
SCHEDULE_TIMES = [f"{h:02d}:{m:02d}" for h in range(6, 23) for m in (0, 30)]
DEFAULT_SCHEDULE_TIME = "09:00"


def _log_path() -> str:
    """Append-only log next to the DB / .exe (writable location)."""
    return os.path.join(os.path.dirname(db.DB_PATH), LOG_FILENAME)


def _log(msg: str) -> None:
    try:
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    except OSError:
        pass


def resource_path(relative: str) -> str:
    """Return an absolute path that works in dev and inside a PyInstaller .exe."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


def open_app_password_guide(parent: tk.Misc) -> None:
    """Open the Gmail App Password PDF in the user's default PDF viewer."""
    lang = i18n.get_language()
    fname = f"gmail_app_password_{lang}.pdf"
    path = resource_path(os.path.join("assets", fname))
    if not os.path.exists(path):
        # Fall back to English if the requested language is missing.
        fallback = resource_path(os.path.join("assets", "gmail_app_password_en.pdf"))
        if os.path.exists(fallback):
            path = fallback
        else:
            messagebox.showerror(
                t("msg.guide_missing.title"),
                t("msg.guide_missing.body", path=path),
                parent=parent)
            return
    try:
        os.startfile(path)  # Windows-only; that's our target platform.
    except OSError as e:
        messagebox.showerror(
            t("msg.guide_missing.title"), str(e), parent=parent)
APP_VERSION = "1.1"

# Colors used to flag rows in the member list
COLOR_OVERDUE = "#ffd6d6"
COLOR_DUE_SOON = "#fff3cd"
COLOR_OK = "#ffffff"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- Helpers ---------------------------------------------------------

def parse_iso(s: str) -> Optional[date]:
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def fmt_human(iso: str) -> str:
    d = parse_iso(iso)
    return d.strftime("%d-%m-%Y") if d else iso


def member_status(m: Member, today: Optional[date] = None) -> str:
    today = today or date.today()
    due = parse_iso(m.next_payment_date)
    if not due:
        return "ok"
    if due < today:
        return "overdue"
    if (due - today).days <= m.reminder_months * 31:
        return "due_soon"
    return "ok"


# ---------- Date picker (3 spinboxes) --------------------------------------

class DatePicker(ttk.Frame):
    """Three spinboxes for day/month/year. No external deps."""

    def __init__(self, master, initial: Optional[date] = None):
        super().__init__(master)
        initial = initial or date.today()
        self.day_var = tk.StringVar(value=f"{initial.day:02d}")
        self.month_var = tk.StringVar(value=f"{initial.month:02d}")
        self.year_var = tk.StringVar(value=str(initial.year))

        opts = {"width": 4, "font": ("Segoe UI", 12)}
        ttk.Label(self, text=t("label.day")).grid(row=0, column=0, padx=2)
        tk.Spinbox(self, from_=1, to=31, textvariable=self.day_var,
                   format="%02.0f", **opts).grid(row=1, column=0, padx=2)
        ttk.Label(self, text=t("label.month")).grid(row=0, column=1, padx=2)
        tk.Spinbox(self, from_=1, to=12, textvariable=self.month_var,
                   format="%02.0f", **opts).grid(row=1, column=1, padx=2)
        ttk.Label(self, text=t("label.year")).grid(row=0, column=2, padx=2)
        tk.Spinbox(self, from_=2000, to=2100, textvariable=self.year_var,
                   width=6, font=("Segoe UI", 12)).grid(row=1, column=2, padx=2)

    def get_date(self) -> Optional[date]:
        try:
            return date(int(self.year_var.get()),
                       int(self.month_var.get()),
                       int(self.day_var.get()))
        except ValueError:
            return None

    def set_date(self, d: date) -> None:
        self.day_var.set(f"{d.day:02d}")
        self.month_var.set(f"{d.month:02d}")
        self.year_var.set(str(d.year))


# ---------- Member dialog ---------------------------------------------------

class MemberDialog(tk.Toplevel):
    """Modal dialog used for both Add and Edit."""

    def __init__(self, master, member: Optional[Member] = None):
        super().__init__(master)
        self.result: Optional[Member] = None
        self.member = member
        self.title(t("dlg.edit_member") if member else t("dlg.add_member"))
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        self.configure(padx=20, pady=20)

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        big = ("Segoe UI", 12)

        ttk.Label(body, text=t("label.name"), font=big).grid(row=0, column=0, sticky="w", pady=6)
        self.name_var = tk.StringVar(value=member.name if member else "")
        ttk.Entry(body, textvariable=self.name_var, font=big, width=32
                  ).grid(row=0, column=1, sticky="we", pady=6, padx=(10, 0))

        ttk.Label(body, text=t("label.email"), font=big).grid(row=1, column=0, sticky="w", pady=6)
        self.email_var = tk.StringVar(value=member.email if member else "")
        ttk.Entry(body, textvariable=self.email_var, font=big, width=32
                  ).grid(row=1, column=1, sticky="we", pady=6, padx=(10, 0))

        ttk.Label(body, text=t("label.paid_on"), font=big).grid(row=2, column=0, sticky="w", pady=6)
        self.paid_picker = DatePicker(
            body, initial=parse_iso(member.paid_date) if member else date.today())
        self.paid_picker.grid(row=2, column=1, sticky="w", pady=6, padx=(10, 0))

        ttk.Label(body, text=t("label.next_payment"), font=big
                  ).grid(row=3, column=0, sticky="w", pady=6)
        default_next = (parse_iso(member.next_payment_date)
                        if member else date.today() + timedelta(days=365))
        self.next_picker = DatePicker(body, initial=default_next)
        self.next_picker.grid(row=3, column=1, sticky="w", pady=6, padx=(10, 0))

        ttk.Label(body, text=t("label.remind"), font=big
                  ).grid(row=4, column=0, sticky="w", pady=6)
        self.reminder_var = tk.IntVar(value=member.reminder_months if member else 1)
        rfrm = ttk.Frame(body)
        rfrm.grid(row=4, column=1, sticky="w", pady=6, padx=(10, 0))
        for i, key in enumerate(("reminder.1mo", "reminder.2mo", "reminder.3mo")):
            ttk.Radiobutton(rfrm, text=t(key), value=i + 1,
                            variable=self.reminder_var).grid(row=0, column=i, padx=(0, 12))

        ttk.Label(body, text=t("label.notes"), font=big
                  ).grid(row=5, column=0, sticky="nw", pady=6)
        self.notes_text = tk.Text(body, width=32, height=4, font=big, wrap="word")
        if member:
            self.notes_text.insert("1.0", member.notes)
        self.notes_text.grid(row=5, column=1, sticky="we", pady=6, padx=(10, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(16, 0))
        ttk.Button(btns, text=t("btn.cancel"), command=self._on_cancel
                   ).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text=t("btn.save"), command=self._on_save,
                   style="Accent.TButton").pack(side="right")

        self.bind("<Return>", lambda _e: self._on_save())
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._center_on(master)

    def _center_on(self, master) -> None:
        self.update_idletasks()
        mx = master.winfo_rootx()
        my = master.winfo_rooty()
        mw = master.winfo_width()
        mh = master.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{mx + (mw - w) // 2}+{my + (mh - h) // 2}")

    def _on_save(self) -> None:
        name = self.name_var.get().strip()
        email = self.email_var.get().strip()
        paid = self.paid_picker.get_date()
        nxt = self.next_picker.get_date()
        notes = self.notes_text.get("1.0", "end").strip()

        if not name:
            messagebox.showwarning(t("msg.missing_name.title"),
                                   t("msg.missing_name.body"), parent=self)
            return
        if not EMAIL_RE.match(email):
            messagebox.showwarning(t("msg.invalid_email.title"),
                                   t("msg.invalid_email.body"), parent=self)
            return
        if not paid:
            messagebox.showwarning(t("msg.invalid_date.title"),
                                   t("msg.invalid_paid_date.body"), parent=self)
            return
        if not nxt:
            messagebox.showwarning(t("msg.invalid_date.title"),
                                   t("msg.invalid_next_date.body"), parent=self)
            return
        if nxt < paid:
            messagebox.showwarning(t("msg.date_order.title"),
                                   t("msg.date_order.body"), parent=self)
            return

        self.result = Member(
            id=self.member.id if self.member else None,
            name=name,
            email=email,
            paid_date=paid.isoformat(),
            next_payment_date=nxt.isoformat(),
            reminder_months=int(self.reminder_var.get()),
            notes=notes,
        )
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


# ---------- Email Settings dialog ------------------------------------------

SMTP_PRESETS = {
    "Gmail":              ("smtp.gmail.com",     587, "starttls"),
    "Outlook / Hotmail":  ("smtp.office365.com", 587, "starttls"),
    "Yahoo":              ("smtp.mail.yahoo.com", 587, "starttls"),
    "Custom":             ("",                   587, "starttls"),
}


class EmailSettingsDialog(tk.Toplevel):
    """Lets the owner enter SMTP credentials once. Stored in the local DB."""

    def __init__(self, master):
        super().__init__(master)
        self.result_saved = False
        self.title(t("dlg.email_settings"))
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        self.configure(padx=20, pady=20)

        s = mailer.load_settings()

        big = ("Segoe UI", 11)
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        row = 0

        ttk.Label(body, text=t("label.club_name"), font=big
                  ).grid(row=row, column=0, sticky="w", pady=4)
        self.club_var = tk.StringVar(value=s.club_name)
        ttk.Entry(body, textvariable=self.club_var, font=big, width=36
                  ).grid(row=row, column=1, columnspan=2, sticky="we", pady=4, padx=(10, 0))
        row += 1

        ttk.Label(body, text=t("label.sender_name"), font=big
                  ).grid(row=row, column=0, sticky="w", pady=4)
        self.sender_name_var = tk.StringVar(value=s.sender_name)
        ttk.Entry(body, textvariable=self.sender_name_var, font=big, width=36
                  ).grid(row=row, column=1, columnspan=2, sticky="we", pady=4, padx=(10, 0))
        row += 1

        ttk.Label(body, text=t("label.sender_email"), font=big
                  ).grid(row=row, column=0, sticky="w", pady=4)
        self.sender_email_var = tk.StringVar(value=s.sender_email)
        ttk.Entry(body, textvariable=self.sender_email_var, font=big, width=36
                  ).grid(row=row, column=1, columnspan=2, sticky="we", pady=4, padx=(10, 0))
        row += 1

        ttk.Label(body, text=t("label.provider"), font=big
                  ).grid(row=row, column=0, sticky="w", pady=4)
        self.preset_var = tk.StringVar(value=self._detect_preset(s))
        preset_cb = ttk.Combobox(body, textvariable=self.preset_var, font=big, width=34,
                                 values=list(SMTP_PRESETS.keys()), state="readonly")
        preset_cb.grid(row=row, column=1, columnspan=2, sticky="we", pady=4, padx=(10, 0))
        preset_cb.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset())
        row += 1

        ttk.Label(body, text=t("label.smtp_host"), font=big
                  ).grid(row=row, column=0, sticky="w", pady=4)
        self.smtp_host_var = tk.StringVar(value=s.smtp_host)
        ttk.Entry(body, textvariable=self.smtp_host_var, font=big, width=24
                  ).grid(row=row, column=1, sticky="we", pady=4, padx=(10, 0))
        ttk.Label(body, text=t("label.port"), font=big
                  ).grid(row=row, column=2, sticky="e", pady=4, padx=(8, 0))
        self.smtp_port_var = tk.StringVar(value=str(s.smtp_port))
        ttk.Entry(body, textvariable=self.smtp_port_var, font=big, width=6
                  ).grid(row=row, column=3, sticky="w", pady=4, padx=(4, 0))
        row += 1

        ttk.Label(body, text=t("label.security"), font=big
                  ).grid(row=row, column=0, sticky="w", pady=4)
        self.security_var = tk.StringVar(value=s.smtp_security)
        sec_frame = ttk.Frame(body)
        sec_frame.grid(row=row, column=1, columnspan=3, sticky="w", pady=4, padx=(10, 0))
        for label, value in (("STARTTLS", "starttls"), ("SSL", "ssl"), ("None", "none")):
            ttk.Radiobutton(sec_frame, text=label, value=value,
                            variable=self.security_var).pack(side="left", padx=(0, 10))
        row += 1

        ttk.Label(body, text=t("label.smtp_user"), font=big
                  ).grid(row=row, column=0, sticky="w", pady=4)
        self.smtp_user_var = tk.StringVar(value=s.smtp_user or s.sender_email)
        ttk.Entry(body, textvariable=self.smtp_user_var, font=big, width=36
                  ).grid(row=row, column=1, columnspan=2, sticky="we", pady=4, padx=(10, 0))
        row += 1

        ttk.Label(body, text=t("label.smtp_pass"), font=big
                  ).grid(row=row, column=0, sticky="w", pady=4)
        self.smtp_pass_var = tk.StringVar(value=s.smtp_password)
        self.pass_entry = ttk.Entry(body, textvariable=self.smtp_pass_var,
                                    font=big, width=30, show="•")
        self.pass_entry.grid(row=row, column=1, sticky="we", pady=4, padx=(10, 0))
        self.show_pass_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(body, text=t("btn.show"), variable=self.show_pass_var,
                        command=self._toggle_pass).grid(row=row, column=2, sticky="w",
                                                       padx=(8, 0))
        row += 1

        # Clickable "How do I get this password?" link → opens bundled PDF.
        link = tk.Label(body, text=t("label.how_to_get_pass"),
                        font=("Segoe UI", 10, "underline"),
                        foreground="#1565c0", cursor="hand2")
        link.grid(row=row, column=1, columnspan=2, sticky="w",
                  pady=(2, 6), padx=(10, 0))
        link.bind("<Button-1>", lambda _e: open_app_password_guide(self))
        row += 1

        ttk.Label(body, text=t("email.help"), font=("Segoe UI", 9),
                  foreground="#555", wraplength=460, justify="left"
                  ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(4, 8))
        row += 1

        self.auto_var = tk.BooleanVar(value=s.auto_send_enabled)
        ttk.Checkbutton(body, text=t("label.auto_send"),
                        variable=self.auto_var).grid(row=row, column=0, columnspan=3,
                                                     sticky="w", pady=4)
        row += 1

        # ---- Automation section ----------------------------------------
        ttk.Separator(body, orient="horizontal").grid(
            row=row, column=0, columnspan=4, sticky="we", pady=(12, 6))
        row += 1
        ttk.Label(body, text=t("auto.section"),
                  font=("Segoe UI Semibold", 11)).grid(
            row=row, column=0, columnspan=4, sticky="w", pady=(0, 4))
        row += 1

        # Start with Windows
        self.startup_var = tk.BooleanVar(value=autorun.is_startup_enabled())
        ttk.Checkbutton(body, text=t("auto.startup"),
                        variable=self.startup_var
                        ).grid(row=row, column=0, columnspan=4,
                               sticky="w", pady=2)
        row += 1

        # Daily scheduled task — checkbox + time picker on same row
        self.daily_var = tk.BooleanVar(value=autorun.is_scheduled_task_enabled())
        ttk.Checkbutton(body, text=t("auto.daily"), variable=self.daily_var
                        ).grid(row=row, column=0, columnspan=2,
                               sticky="w", pady=2)
        current_time = autorun.get_scheduled_task_time() or DEFAULT_SCHEDULE_TIME
        if current_time not in SCHEDULE_TIMES:
            current_time = DEFAULT_SCHEDULE_TIME
        self.daily_time_var = tk.StringVar(value=current_time)
        ttk.Combobox(body, textvariable=self.daily_time_var, font=big,
                     values=SCHEDULE_TIMES, state="readonly", width=8
                     ).grid(row=row, column=2, sticky="w", pady=2, padx=(8, 0))
        row += 1

        ttk.Label(body, text=t("auto.daily.note"), font=("Segoe UI", 9),
                  foreground="#555", wraplength=460, justify="left"
                  ).grid(row=row, column=0, columnspan=4, sticky="w",
                         pady=(2, 0), padx=(20, 0))
        row += 1

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(16, 0))
        ttk.Button(btns, text=t("btn.test_email"), command=self._on_test
                   ).pack(side="left")
        ttk.Button(btns, text=t("btn.cancel"), command=self.destroy
                   ).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text=t("btn.save"), style="Accent.TButton",
                   command=self._on_save).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())

    @staticmethod
    def _detect_preset(s: EmailSettings) -> str:
        for name, (host, port, sec) in SMTP_PRESETS.items():
            if host and s.smtp_host == host:
                return name
        return "Custom"

    def _apply_preset(self) -> None:
        name = self.preset_var.get()
        host, port, sec = SMTP_PRESETS.get(name, ("", 587, "starttls"))
        if host:
            self.smtp_host_var.set(host)
        self.smtp_port_var.set(str(port))
        self.security_var.set(sec)

    def _toggle_pass(self) -> None:
        self.pass_entry.configure(show="" if self.show_pass_var.get() else "•")

    def _collect(self) -> Optional[EmailSettings]:
        try:
            port = int(self.smtp_port_var.get())
        except ValueError:
            messagebox.showwarning(t("msg.invalid_port.title"),
                                   t("msg.invalid_port.body"), parent=self)
            return None
        s = EmailSettings(
            club_name=self.club_var.get().strip(),
            sender_name=self.sender_name_var.get().strip(),
            sender_email=self.sender_email_var.get().strip(),
            smtp_host=self.smtp_host_var.get().strip(),
            smtp_port=port,
            smtp_user=self.smtp_user_var.get().strip(),
            smtp_password=self.smtp_pass_var.get(),
            smtp_security=self.security_var.get(),
            auto_send_enabled=bool(self.auto_var.get()),
        )
        if not EMAIL_RE.match(s.sender_email):
            messagebox.showwarning(t("msg.invalid_email.title"),
                                   t("msg.invalid_email.body"), parent=self)
            return None
        if not s.smtp_host or not s.smtp_user or not s.smtp_password:
            messagebox.showwarning(t("msg.missing_fields.title"),
                                   t("msg.missing_fields.body"), parent=self)
            return None
        return s

    def _on_save(self) -> None:
        s = self._collect()
        if not s:
            return
        mailer.save_settings(s)
        if not self._apply_automation():
            return  # user saw an error; keep dialog open so they can adjust
        self.result_saved = True
        self.destroy()

    def _apply_automation(self) -> bool:
        """Apply the two Windows-automation toggles. Return True on success."""
        try:
            if self.startup_var.get():
                autorun.enable_startup()
            else:
                autorun.disable_startup()

            if self.daily_var.get():
                autorun.enable_scheduled_task(self.daily_time_var.get())
            else:
                autorun.disable_scheduled_task()
        except (RuntimeError, OSError) as e:
            messagebox.showerror(
                t("auto.error.title"),
                t("auto.error.body", error=str(e)),
                parent=self)
            return False
        return True

    def _on_test(self) -> None:
        s = self._collect()
        if not s:
            return
        to = simpledialog.askstring(
            t("msg.test_prompt.title"),
            t("msg.test_prompt.body"),
            initialvalue=s.sender_email, parent=self)
        if not to:
            return

        for w in self.winfo_children():
            try:
                w.configure(state="disabled")
            except tk.TclError:
                pass
        self.config(cursor="wait")

        def worker():
            err: Optional[str] = None
            try:
                mailer.send_test(to, s)
            except mailer.MailerError as e:
                err = str(e)
            self.after(0, lambda: self._test_done(err, to))

        threading.Thread(target=worker, daemon=True).start()

    def _test_done(self, err: Optional[str], to: str) -> None:
        self.config(cursor="")
        for w in self.winfo_children():
            try:
                w.configure(state="normal")
            except tk.TclError:
                pass
        if err:
            messagebox.showerror(t("msg.test_failed.title"), err, parent=self)
        else:
            messagebox.showinfo(t("msg.test_sent.title"),
                                t("msg.test_sent.body", to=to), parent=self)


# ---------- Tray icon -------------------------------------------------------

def _build_tray_image():
    """Return a 64×64 PIL.Image used as the tray icon."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 60, 60), radius=12, fill="#1565c0")
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), "C", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((64 - w) // 2 - bbox[0], (64 - h) // 2 - bbox[1] - 2),
           "C", fill="white", font=font)
    return img


# ---------- Headless --send-only mode --------------------------------------

def run_headless() -> None:
    """No GUI: load config, send any pending reminders, exit.

    Invoked by the daily Windows scheduled task. Logs every run to
    ``clubmanager.log`` next to the DB so the user can see what happened.
    """
    db.init_db()
    i18n.set_language(db.get_setting("language", i18n.DEFAULT_LANG))
    _log("--send-only: starting reminder check")
    try:
        result = mailer.process_pending()
    except Exception as e:  # noqa: BLE001
        _log(f"--send-only: ERROR {e}")
        return
    if result.skipped_no_config:
        _log("--send-only: skipped — email not configured")
        return
    _log(f"--send-only: sent={len(result.sent)} failed={len(result.failed)}")
    for n in result.sent:
        _log(f"  sent  -> {n}")
    for n, e in result.failed:
        _log(f"  fail  -> {n}: {e}")


# ---------- Main window -----------------------------------------------------

class App(tk.Tk):
    def __init__(self, start_in_tray: bool = False):
        super().__init__()
        self.geometry("1000x620")
        self.minsize(820, 480)

        self.tray_icon = None  # set by _setup_tray()

        self._setup_style()
        self._build_ui()
        self.refresh()
        self._setup_tray()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if start_in_tray:
            # Hide the window on startup; tray icon remains visible.
            self.withdraw()
        self.after(800, lambda: self._kick_auto_send(manual=False))

    # -- tray ------------------------------------------------------------
    def _setup_tray(self) -> None:
        try:
            import pystray
        except ImportError:
            _log("pystray not installed — tray icon disabled")
            return

        def show_action(_icon=None, _item=None):
            self.after(0, self._tray_show)

        def check_action(_icon=None, _item=None):
            self.after(0, lambda: self._kick_auto_send(manual=True))

        def quit_action(_icon=None, _item=None):
            self.after(0, self._tray_quit)

        menu = pystray.Menu(
            pystray.MenuItem(t("tray.show"), show_action, default=True),
            pystray.MenuItem(t("tray.check_now"), check_action),
            pystray.MenuItem(t("tray.quit"), quit_action),
        )
        self.tray_icon = pystray.Icon(
            "ClubManager", _build_tray_image(), t("tray.tooltip"), menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_show(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_quit(self) -> None:
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        self.destroy()

    def _on_close(self) -> None:
        # X button: hide to tray if available, otherwise really quit.
        if self.tray_icon is not None:
            self.withdraw()
        else:
            self.destroy()

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Treeview", font=("Segoe UI", 11), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 11))
        style.configure("Toolbar.TButton", font=("Segoe UI", 11), padding=(14, 8))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 11),
                        padding=(14, 8))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 18))
        style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#555")

    # -- layout ----------------------------------------------------------
    def _build_ui(self) -> None:
        self.title(f"{t('app.title')} — v{APP_VERSION}")

        # Header
        header = ttk.Frame(self, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text=t("app.title"), style="Title.TLabel").pack(side="left")

        # Language picker (top-right)
        lang_frame = ttk.Frame(header)
        lang_frame.pack(side="right")
        ttk.Label(lang_frame, text=t("header.language"), font=("Segoe UI", 10)
                  ).pack(side="left", padx=(0, 6))
        self.lang_var = tk.StringVar(value=i18n.LANGUAGES[i18n.get_language()])
        lang_cb = ttk.Combobox(lang_frame, textvariable=self.lang_var,
                               values=list(i18n.LANGUAGES.values()),
                               state="readonly", width=10, font=("Segoe UI", 10))
        lang_cb.pack(side="left")
        lang_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_change_language())

        self.status_label = ttk.Label(header, text="", style="Sub.TLabel")
        self.status_label.pack(side="right", padx=(0, 16))

        # Toolbar
        toolbar = ttk.Frame(self, padding=(16, 0, 16, 8))
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text=t("btn.add_member"), style="Accent.TButton",
                   command=self.on_add).pack(side="left")
        ttk.Button(toolbar, text=t("btn.edit"), style="Toolbar.TButton",
                   command=self.on_edit).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text=t("btn.delete"), style="Toolbar.TButton",
                   command=self.on_delete).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text=t("btn.mark_paid"), style="Toolbar.TButton",
                   command=self.on_mark_paid).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text=t("btn.email_settings"), style="Toolbar.TButton",
                   command=self.on_email_settings).pack(side="left", padx=(24, 0))
        ttk.Button(toolbar, text=t("btn.check_now"), style="Toolbar.TButton",
                   command=lambda: self._kick_auto_send(manual=True)
                   ).pack(side="left", padx=(8, 0))

        ttk.Label(toolbar, text=t("label.search"), font=("Segoe UI", 11)
                  ).pack(side="left", padx=(24, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(toolbar, textvariable=self.search_var, font=("Segoe UI", 11),
                  width=24).pack(side="left")

        # Member list
        list_frame = ttk.Frame(self, padding=(16, 0, 16, 16))
        list_frame.pack(fill="both", expand=True)

        cols = ("name", "email", "paid", "next", "remind", "status")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings",
                                 selectmode="browse")
        headings = {
            "name":   (t("col.name"), 220),
            "email":  (t("col.email"), 240),
            "paid":   (t("col.paid"), 110),
            "next":   (t("col.next"), 130),
            "remind": (t("col.remind"), 110),
            "status": (t("col.status"), 130),
        }
        for k, (label, width) in headings.items():
            self.tree.heading(k, text=label)
            self.tree.column(k, width=width, anchor="w")

        self.tree.tag_configure("overdue", background=COLOR_OVERDUE)
        self.tree.tag_configure("due_soon", background=COLOR_DUE_SOON)
        self.tree.tag_configure("ok", background=COLOR_OK)

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self.on_edit())

        # Footer legend
        footer = ttk.Frame(self, padding=(16, 0, 16, 12))
        footer.pack(fill="x")
        self._legend_swatch(footer, COLOR_OVERDUE, t("status.overdue"))
        self._legend_swatch(footer, COLOR_DUE_SOON, t("status.due_soon"))
        self._legend_swatch(footer, COLOR_OK, t("status.ok"))

    def _legend_swatch(self, parent, color: str, label: str) -> None:
        wrap = ttk.Frame(parent)
        wrap.pack(side="left", padx=(0, 16))
        sw = tk.Frame(wrap, width=18, height=14, bg=color,
                      highlightbackground="#888", highlightthickness=1)
        sw.pack(side="left")
        ttk.Label(wrap, text=" " + label, font=("Segoe UI", 10)).pack(side="left")

    # -- language change -------------------------------------------------
    def _on_change_language(self) -> None:
        picked = self.lang_var.get()
        code = next((c for c, name in i18n.LANGUAGES.items() if name == picked),
                    i18n.DEFAULT_LANG)
        if code == i18n.get_language():
            return
        i18n.set_language(code)
        db.set_setting("language", code)
        # Tear down existing widgets and rebuild from scratch in the new language.
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self.refresh()

    # -- data ------------------------------------------------------------
    def refresh(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        members = db.list_members(self.search_var.get().strip())
        today = date.today()
        overdue = due_soon = 0
        for m in members:
            status = member_status(m, today)
            if status == "overdue":
                overdue += 1
                status_text = t("status.overdue")
            elif status == "due_soon":
                due_soon += 1
                status_text = t("status.due_soon")
            else:
                status_text = t("status.ok")
            self.tree.insert(
                "", "end", iid=str(m.id),
                values=(m.name, m.email, fmt_human(m.paid_date),
                        fmt_human(m.next_payment_date),
                        t("remind.short_mo", n=m.reminder_months),
                        status_text),
                tags=(status,))
        self.status_label.config(
            text=t("status.summary",
                   total=len(members), overdue=overdue, due=due_soon))

    def _selected_member(self) -> Optional[Member]:
        sel = self.tree.selection()
        if not sel:
            return None
        return db.get_member(int(sel[0]))

    # -- actions ---------------------------------------------------------
    def on_add(self) -> None:
        dlg = MemberDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            db.add_member(dlg.result)
            self.refresh()

    def on_edit(self) -> None:
        m = self._selected_member()
        if not m:
            messagebox.showinfo(t("msg.no_selection.title"),
                                t("msg.no_selection.body"))
            return
        dlg = MemberDialog(self, member=m)
        self.wait_window(dlg)
        if dlg.result:
            db.update_member(dlg.result)
            self.refresh()

    def on_delete(self) -> None:
        m = self._selected_member()
        if not m:
            messagebox.showinfo(t("msg.no_selection.title"),
                                t("msg.no_selection.body"))
            return
        if messagebox.askyesno(t("msg.delete.title"),
                               t("msg.delete.body", name=m.name)):
            db.delete_member(m.id)  # type: ignore[arg-type]
            self.refresh()

    def on_mark_paid(self) -> None:
        m = self._selected_member()
        if not m:
            messagebox.showinfo(t("msg.no_selection.title"),
                                t("msg.no_selection.body"))
            return
        today = date.today()
        try:
            next_year = today.replace(year=today.year + 1)
        except ValueError:
            next_year = today + timedelta(days=365)
        if not messagebox.askyesno(
                t("msg.mark_paid.title"),
                t("msg.mark_paid.body",
                  name=m.name, date=next_year.strftime("%d-%m-%Y"))):
            return
        m.paid_date = today.isoformat()
        m.next_payment_date = next_year.isoformat()
        db.update_member(m)
        self.refresh()

    # -- email settings --------------------------------------------------
    def on_email_settings(self) -> None:
        dlg = EmailSettingsDialog(self)
        self.wait_window(dlg)
        if dlg.result_saved:
            self._kick_auto_send(manual=True)

    # -- automatic reminder dispatch ------------------------------------
    def _kick_auto_send(self, manual: bool = False) -> None:
        settings = mailer.load_settings()
        if not settings.is_configured():
            if manual:
                messagebox.showinfo(t("msg.email_not_set.title"),
                                    t("msg.email_not_set.body"))
            self._schedule_next_check()
            return
        if not settings.auto_send_enabled and not manual:
            self._schedule_next_check()
            return

        self.status_label.config(text=t("status.checking"))

        def worker():
            try:
                result = mailer.process_pending()
            except Exception as e:  # noqa: BLE001 — surface any error to UI
                result = mailer.DispatchResult(sent=[], failed=[("internal", str(e))])
            self.after(0, lambda: self._auto_send_done(result, manual))

        threading.Thread(target=worker, daemon=True).start()

    def _auto_send_done(self, result: "mailer.DispatchResult", manual: bool) -> None:
        self.refresh()
        self._schedule_next_check()

        if result.skipped_no_config:
            return
        if not result.sent and not result.failed:
            if manual:
                messagebox.showinfo(t("msg.reminders.title"),
                                    t("msg.reminders.none"))
            return

        parts = []
        if result.sent:
            parts.append(t("msg.reminders.sent_header")
                         + "\n  • " + "\n  • ".join(result.sent))
        if result.failed:
            fails = "\n  • ".join(f"{n}: {e}" for n, e in result.failed)
            parts.append(t("msg.reminders.failed_header") + "\n  • " + fails)
        msg = "\n\n".join(parts)
        if result.failed:
            messagebox.showerror(t("msg.reminders.title"), msg)
        elif manual or result.sent:
            messagebox.showinfo(t("msg.reminders.title"), msg)

    def _schedule_next_check(self) -> None:
        self.after(AUTO_SEND_INTERVAL_MS, lambda: self._kick_auto_send(manual=False))


# ---------- Entry point -----------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    if "--send-only" in args:
        run_headless()
        return

    db.init_db()
    i18n.set_language(db.get_setting("language", i18n.DEFAULT_LANG))
    app = App(start_in_tray="--tray" in args)
    app.mainloop()


if __name__ == "__main__":
    main()
