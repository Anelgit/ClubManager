"""Email sending for the Club Manager app.

* Settings live in the ``settings`` table of ``club.db`` (one row per key).
* The SMTP password is stored base64-obfuscated. NOTE: this is *obfuscation*,
  not real encryption. The DB lives on the user's own PC; anyone with file
  access could decode it. We accept this trade-off to keep the app
  dependency-free (no ``cryptography`` / ``keyring``).
* All sending is synchronous — the GUI calls these from a worker thread.
"""
from __future__ import annotations

import base64
import smtplib
import ssl
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

import db
import i18n
from db import Member


# ---------- Settings model -------------------------------------------------

SETTING_KEYS = (
    "club_name",
    "sender_name",
    "sender_email",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_password",   # stored base64-obfuscated
    "smtp_security",   # "starttls" | "ssl" | "none"
    "auto_send_enabled",
)


@dataclass
class EmailSettings:
    club_name: str = ""
    sender_name: str = ""
    sender_email: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""           # plaintext in memory only
    smtp_security: str = "starttls"   # starttls / ssl / none
    auto_send_enabled: bool = False

    def is_configured(self) -> bool:
        return bool(self.sender_email and self.smtp_host
                    and self.smtp_user and self.smtp_password)


def _obfuscate(plain: str) -> str:
    return base64.b64encode(plain.encode("utf-8")).decode("ascii")


def _deobfuscate(stored: str) -> str:
    if not stored:
        return ""
    try:
        return base64.b64decode(stored.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def load_settings() -> EmailSettings:
    raw = db.get_all_settings()
    return EmailSettings(
        club_name=raw.get("club_name", ""),
        sender_name=raw.get("sender_name", ""),
        sender_email=raw.get("sender_email", ""),
        smtp_host=raw.get("smtp_host", "smtp.gmail.com"),
        smtp_port=int(raw.get("smtp_port", "587") or 587),
        smtp_user=raw.get("smtp_user", ""),
        smtp_password=_deobfuscate(raw.get("smtp_password", "")),
        smtp_security=raw.get("smtp_security", "starttls"),
        auto_send_enabled=raw.get("auto_send_enabled", "0") == "1",
    )


def save_settings(s: EmailSettings) -> None:
    db.set_setting("club_name", s.club_name)
    db.set_setting("sender_name", s.sender_name)
    db.set_setting("sender_email", s.sender_email)
    db.set_setting("smtp_host", s.smtp_host)
    db.set_setting("smtp_port", str(int(s.smtp_port)))
    db.set_setting("smtp_user", s.smtp_user)
    db.set_setting("smtp_password", _obfuscate(s.smtp_password))
    db.set_setting("smtp_security", s.smtp_security)
    db.set_setting("auto_send_enabled", "1" if s.auto_send_enabled else "0")


# ---------- Message template (language-aware) -----------------------------

def _fmt_date(d: date) -> str:
    return d.strftime("%d.%m.%Y.")


def _when_phrase(member: Member, days_until: int) -> str:
    """The "in X" phrase substituted into the upcoming-renewal body."""
    if days_until <= 7:
        return i18n.days_word(days_until)
    return i18n.t(f"when.approx_{member.reminder_months}mo")


def compose_reminder(member: Member, settings: EmailSettings,
                     today: Optional[date] = None) -> EmailMessage:
    today = today or date.today()
    due = date.fromisoformat(member.next_payment_date)
    days = (due - today).days
    club = settings.club_name or ("Club" if i18n.get_language() == "en" else "Klub")

    greeting = i18n.t("email.greeting", name=member.name)
    thanks = i18n.t("email.thanks")
    sign_off = i18n.t("email.sign_off")

    if days < 0:
        subject = i18n.t("email.subject_overdue", club=club)
        middle = i18n.t("email.body_overdue",
                        due=_fmt_date(due), ago=i18n.days_word(abs(days)))
    else:
        subject = i18n.t("email.subject_upcoming", club=club)
        middle = i18n.t("email.body_upcoming",
                        due=_fmt_date(due),
                        when=_when_phrase(member, days))

    body = f"{greeting}\n\n{middle}\n\n{thanks}\n\n{sign_off}\n{club}"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.sender_name or club, settings.sender_email))
    msg["To"] = member.email
    msg.set_content(body)
    return msg


# ---------- Sending --------------------------------------------------------

class MailerError(Exception):
    pass


def _open_smtp(s: EmailSettings) -> smtplib.SMTP:
    ctx = ssl.create_default_context()
    if s.smtp_security == "ssl":
        srv: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port,
                                             context=ctx, timeout=30)
    else:
        srv = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=30)
        srv.ehlo()
        if s.smtp_security == "starttls":
            srv.starttls(context=ctx)
            srv.ehlo()
    srv.login(s.smtp_user, s.smtp_password)
    return srv


def send_message(msg: EmailMessage, s: EmailSettings) -> None:
    try:
        srv = _open_smtp(s)
    except (smtplib.SMTPException, OSError) as e:
        raise MailerError(f"Cannot connect / login to mail server: {e}") from e
    try:
        srv.send_message(msg)
    except smtplib.SMTPException as e:
        raise MailerError(f"Send failed: {e}") from e
    finally:
        try:
            srv.quit()
        except Exception:
            pass


def send_test(to_addr: str, s: EmailSettings) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Test – Club Manager"
    msg["From"] = formataddr((s.sender_name or "Club Manager", s.sender_email))
    msg["To"] = to_addr
    if i18n.get_language() == "bs":
        msg.set_content(
            "Ovo je testna poruka iz aplikacije Club Manager.\n"
            "Ako vidite ovu poruku, slanje e-pošte je ispravno podešeno."
        )
    else:
        msg.set_content(
            "This is a test message from Club Manager.\n"
            "If you can read this, email sending is configured correctly."
        )
    send_message(msg, s)


# ---------- Scheduling / dispatch -----------------------------------------

def _reminder_threshold(due: date, months: int) -> date:
    """Return the date at which a reminder ``months`` months before ``due``
    becomes active. Uses calendar-month math, clipping the day to the
    last valid day of the resulting month."""
    y = due.year
    m = due.month - months
    while m <= 0:
        m += 12
        y -= 1
    d = min(due.day, monthrange(y, m)[1])
    return date(y, m, d)


def should_send_now(member: Member, today: Optional[date] = None) -> bool:
    today = today or date.today()
    try:
        due = date.fromisoformat(member.next_payment_date)
    except ValueError:
        return False
    if member.last_reminder_sent_for == member.next_payment_date:
        return False  # already emailed for this cycle
    threshold = _reminder_threshold(due, member.reminder_months)
    return today >= threshold


@dataclass
class DispatchResult:
    sent: list[str]                # member names successfully emailed
    failed: list[tuple[str, str]]  # (member name, error message)
    skipped_no_config: bool = False


def process_pending(today: Optional[date] = None) -> DispatchResult:
    """Send reminders to every member who's in their window and hasn't yet
    been emailed for this payment cycle. Safe to call repeatedly."""
    today = today or date.today()
    s = load_settings()
    if not s.is_configured() or not s.auto_send_enabled:
        return DispatchResult(sent=[], failed=[], skipped_no_config=True)

    result = DispatchResult(sent=[], failed=[])
    pending = [m for m in db.list_members() if should_send_now(m, today)]
    if not pending:
        return result

    try:
        srv = _open_smtp(s)
    except (smtplib.SMTPException, OSError) as e:
        # Connection failed once → mark all as failed, no retry this round
        for m in pending:
            result.failed.append((m.name, f"connect/login: {e}"))
        return result

    try:
        for m in pending:
            try:
                msg = compose_reminder(m, s, today)
                srv.send_message(msg)
                db.mark_reminder_sent(m.id, m.next_payment_date)  # type: ignore[arg-type]
                result.sent.append(m.name)
            except smtplib.SMTPException as e:
                result.failed.append((m.name, str(e)))
    finally:
        try:
            srv.quit()
        except Exception:
            pass
    return result
