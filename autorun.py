"""Windows automation helpers.

Two independent features the user can toggle from inside the app:

1. **Start with Windows** — writes a value to HKCU\\...\\Run so Club
   Manager launches in tray mode every time the user logs in.
   Uses ``winreg`` (stdlib).

2. **Daily scheduled task** — registers a Task Scheduler job that runs
   ``ClubManager.exe --send-only`` once a day. The app silently sends
   any due reminders and exits, even if the user never opens the GUI.
   Uses ``schtasks.exe`` (ships with Windows).

Neither feature requires admin rights — both target the current user.
Errors raise ``RuntimeError`` so the GUI can show a clear message.
"""
from __future__ import annotations

import os
import subprocess
import sys
import winreg
from datetime import datetime
from typing import Optional


_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE_NAME = "ClubManager"
_TASK_NAME = "ClubManager_DailyReminders"

# Keep schtasks/console windows from flashing when called from the GUI.
_NO_WINDOW = 0x08000000


def app_command() -> str:
    """Return the command line used to invoke Club Manager.

    - When frozen (PyInstaller .exe): the .exe path itself.
    - When run from source: ``python.exe main.py`` so testing in dev works.

    Returned as a single string suitable for both ``schtasks /TR`` and the
    HKCU Run registry value (both want one quoted command line).
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "main.py"))
    return f'"{sys.executable}" "{main_py}"'


# ---------- Start-with-Windows (HKCU\\Run) ---------------------------------

def enable_startup() -> None:
    """Register Club Manager to launch in --tray mode at user login."""
    cmd = f"{app_command()} --tray"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, _RUN_VALUE_NAME, 0, winreg.REG_SZ, cmd)


def disable_startup() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0,
                            winreg.KEY_SET_VALUE) as k:
            try:
                winreg.DeleteValue(k, _RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        pass


def is_startup_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH) as k:
            try:
                winreg.QueryValueEx(k, _RUN_VALUE_NAME)
                return True
            except FileNotFoundError:
                return False
    except FileNotFoundError:
        return False


# ---------- Daily scheduled task (schtasks.exe) ---------------------------

def enable_scheduled_task(time_hhmm: str = "09:00") -> None:
    """Create / replace the daily 'send reminders' task at the given time."""
    if not _valid_time(time_hhmm):
        raise RuntimeError(f"Invalid time format: {time_hhmm!r} (need HH:MM)")
    cmd = [
        "schtasks.exe", "/Create",
        "/TN", _TASK_NAME,
        "/TR", f"{app_command()} --send-only",
        "/SC", "DAILY",
        "/ST", time_hhmm,
        "/F",                       # overwrite if it already exists
    ]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            creationflags=_NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError(
            f"schtasks /Create failed (exit {result.returncode}):\n"
            f"{(result.stderr or result.stdout).strip()}")


def disable_scheduled_task() -> None:
    subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", _TASK_NAME, "/F"],
        capture_output=True, creationflags=_NO_WINDOW)


def is_scheduled_task_enabled() -> bool:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", _TASK_NAME],
        capture_output=True, creationflags=_NO_WINDOW)
    return result.returncode == 0


def get_scheduled_task_time() -> Optional[str]:
    """Return the HH:MM the daily task is currently set to, or None."""
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", _TASK_NAME, "/V", "/FO", "LIST"],
        capture_output=True, text=True, creationflags=_NO_WINDOW,
        encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        # schtasks output is locale-dependent — match on a few common labels.
        if label.strip().lower() in ("start time", "starttid", "starttijd"):
            return _normalise_time(value.strip())
    return None


def _valid_time(s: str) -> bool:
    try:
        datetime.strptime(s, "%H:%M")
        return True
    except ValueError:
        return False


def _normalise_time(s: str) -> Optional[str]:
    for fmt in ("%I:%M:%S %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).strftime("%H:%M")
        except ValueError:
            continue
    return None
