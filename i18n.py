"""Tiny in-process translation layer for the Club Manager app.

Usage:
    import i18n
    i18n.set_language("bs")          # done once at startup from saved setting
    label = i18n.t("btn.save")       # → "Sačuvaj"
    msg   = i18n.t("msg.delete_q", name=member.name)

Keep it dependency-free; just dictionaries + ``str.format``.
"""
from __future__ import annotations

from typing import Final


LANGUAGES: Final[dict[str, str]] = {"en": "English", "bs": "Bosanski"}
DEFAULT_LANG: Final[str] = "bs"

_current_lang: str = DEFAULT_LANG


def set_language(code: str) -> None:
    global _current_lang
    if code in LANGUAGES:
        _current_lang = code


def get_language() -> str:
    return _current_lang


def t(key: str, **fmt) -> str:
    entry = STRINGS.get(key)
    if not entry:
        return key  # fall back to the key itself so missing strings are obvious
    s = entry.get(_current_lang) or entry.get("en") or key
    if fmt:
        try:
            return s.format(**fmt)
        except (KeyError, IndexError):
            return s
    return s


def days_word(n: int) -> str:
    """Return ``n`` with the correct word for 'day(s)' in current language.

    Bosnian rule: ends in 1 (but not 11) → "dan"; otherwise → "dana".
    """
    n = abs(n)
    if _current_lang == "bs":
        if n % 10 == 1 and n % 100 != 11:
            return f"{n} dan"
        return f"{n} dana"
    return f"{n} day" if n == 1 else f"{n} days"


# ---------- String table ---------------------------------------------------

STRINGS: Final[dict[str, dict[str, str]]] = {
    # App-level
    "app.title": {
        "en": "Club Membership Manager",
        "bs": "Upravljanje članarinom kluba",
    },
    "header.language": {"en": "Language:", "bs": "Jezik:"},
    "status.summary": {
        "en": "{total} members  •  {overdue} overdue  •  {due} due soon",
        "bs": "{total} članova  •  {overdue} isteklo  •  {due} uskoro ističe",
    },
    "status.checking": {"en": "Checking reminders…", "bs": "Provjeravanje podsjetnika…"},

    # Toolbar buttons
    "btn.add_member": {"en": "+ Add Member", "bs": "+ Dodaj člana"},
    "btn.edit": {"en": "Edit", "bs": "Uredi"},
    "btn.delete": {"en": "Delete", "bs": "Obriši"},
    "btn.mark_paid": {"en": "Mark Paid", "bs": "Označi plaćeno"},
    "btn.email_settings": {"en": "Email Settings", "bs": "Postavke e-pošte"},
    "btn.check_now": {"en": "Check Reminders Now", "bs": "Provjeri podsjetnike sada"},
    "btn.save": {"en": "Save", "bs": "Sačuvaj"},
    "btn.cancel": {"en": "Cancel", "bs": "Otkaži"},
    "btn.test_email": {"en": "Send Test Email", "bs": "Pošalji test email"},
    "btn.show": {"en": "Show", "bs": "Prikaži"},

    # Search
    "label.search": {"en": "Search:", "bs": "Pretraga:"},

    # Table columns
    "col.name": {"en": "Name", "bs": "Ime"},
    "col.email": {"en": "Email", "bs": "Email"},
    "col.paid": {"en": "Paid On", "bs": "Plaćeno"},
    "col.next": {"en": "Next Payment", "bs": "Sljedeća uplata"},
    "col.remind": {"en": "Remind", "bs": "Podsjetnik"},
    "col.status": {"en": "Status", "bs": "Status"},

    # Status / legend
    "status.overdue": {"en": "Overdue", "bs": "Isteklo"},
    "status.due_soon": {"en": "Due soon", "bs": "Uskoro ističe"},
    "status.ok": {"en": "OK", "bs": "U redu"},
    "remind.short_mo": {"en": "{n} mo", "bs": "{n} mj."},

    # Member dialog
    "dlg.add_member": {"en": "Add Member", "bs": "Dodaj člana"},
    "dlg.edit_member": {"en": "Edit Member", "bs": "Uredi člana"},
    "label.name": {"en": "Name", "bs": "Ime"},
    "label.email": {"en": "Email", "bs": "Email"},
    "label.paid_on": {"en": "Paid on", "bs": "Plaćeno"},
    "label.next_payment": {"en": "Next payment", "bs": "Sljedeća uplata"},
    "label.remind": {"en": "Remind", "bs": "Podsjetnik"},
    "label.notes": {"en": "Notes", "bs": "Bilješke"},
    "label.day": {"en": "Day", "bs": "Dan"},
    "label.month": {"en": "Month", "bs": "Mjesec"},
    "label.year": {"en": "Year", "bs": "Godina"},
    "reminder.1mo": {"en": "1 month before", "bs": "1 mjesec prije"},
    "reminder.2mo": {"en": "2 months before", "bs": "2 mjeseca prije"},
    "reminder.3mo": {"en": "3 months before", "bs": "3 mjeseca prije"},

    # Member dialog validation
    "msg.missing_name.title": {"en": "Missing name", "bs": "Nedostaje ime"},
    "msg.missing_name.body": {"en": "Please enter a name.", "bs": "Molimo unesite ime."},
    "msg.invalid_email.title": {"en": "Invalid email", "bs": "Neispravan email"},
    "msg.invalid_email.body": {
        "en": "Please enter a valid email address.",
        "bs": "Molimo unesite ispravnu email adresu.",
    },
    "msg.invalid_date.title": {"en": "Invalid date", "bs": "Neispravan datum"},
    "msg.invalid_paid_date.body": {
        "en": "Paid date is not valid.",
        "bs": "Datum plaćanja nije ispravan.",
    },
    "msg.invalid_next_date.body": {
        "en": "Next payment date is not valid.",
        "bs": "Datum sljedeće uplate nije ispravan.",
    },
    "msg.date_order.title": {"en": "Date order", "bs": "Redoslijed datuma"},
    "msg.date_order.body": {
        "en": "Next payment date must be after paid date.",
        "bs": "Datum sljedeće uplate mora biti nakon datuma plaćanja.",
    },

    # Selection / delete / mark paid
    "msg.no_selection.title": {"en": "No selection", "bs": "Nije odabrano"},
    "msg.no_selection.body": {
        "en": "Please select a member first.",
        "bs": "Molimo prvo odaberite člana.",
    },
    "msg.delete.title": {"en": "Delete member", "bs": "Obriši člana"},
    "msg.delete.body": {
        "en": "Delete {name}?\nThis cannot be undone.",
        "bs": "Obrisati {name}?\nOvo se ne može poništiti.",
    },
    "msg.mark_paid.title": {"en": "Mark paid", "bs": "Označi plaćeno"},
    "msg.mark_paid.body": {
        "en": "Mark {name} as paid today?\nNext payment will be set to {date}.",
        "bs": "Označiti {name} kao plaćeno danas?\nSljedeća uplata bit će postavljena na {date}.",
    },

    # Email settings dialog
    "dlg.email_settings": {"en": "Email Settings", "bs": "Postavke e-pošte"},
    "label.club_name": {"en": "Club name", "bs": "Naziv kluba"},
    "label.sender_name": {"en": "Sender name", "bs": "Ime pošiljaoca"},
    "label.sender_email": {"en": "Sender email", "bs": "Email pošiljaoca"},
    "label.provider": {"en": "Provider", "bs": "Provajder"},
    "label.smtp_host": {"en": "SMTP host", "bs": "SMTP host"},
    "label.port": {"en": "Port", "bs": "Port"},
    "label.security": {"en": "Security", "bs": "Sigurnost"},
    "label.smtp_user": {
        "en": "Login username (if different from email above)",
        "bs": "Korisničko ime (ako se razlikuje od emaila iznad)",
    },
    "label.smtp_pass": {"en": "App password", "bs": "App lozinka"},
    "label.email_login_hint": {
        "en": "This is also your login for Gmail / Outlook",
        "bs": "Ovo je ujedno i Vaše korisničko ime za Gmail / Outlook",
    },
    "label.advanced_settings": {"en": "Advanced settings", "bs": "Napredne postavke"},
    "label.auto_send": {
        "en": "Send reminders automatically",
        "bs": "Šalji podsjetnike automatski",
    },
    "label.how_to_get_pass": {
        "en": "How do I get this password?",
        "bs": "Kako dobiti ovu lozinku?",
    },
    "msg.guide_missing.title": {"en": "Guide not found", "bs": "Vodič nije pronađen"},
    "msg.guide_missing.body": {
        "en": "The PDF guide could not be found at:\n{path}",
        "bs": "PDF vodič nije pronađen na:\n{path}",
    },
    "email.help": {
        "en": ("For Gmail / Outlook with 2-step verification you must create an "
               "“App password” and paste it above (not your normal "
               "password).\nGmail: myaccount.google.com → Security → App passwords"),
        "bs": ("Za Gmail / Outlook sa dvostrukom potvrdom morate kreirati "
               "„App password” (lozinku za aplikaciju) i unijeti je "
               "iznad (ne svoju običnu lozinku).\n"
               "Gmail: myaccount.google.com → Sigurnost → App passwords"),
    },
    "msg.invalid_port.title": {"en": "Invalid port", "bs": "Neispravan port"},
    "msg.invalid_port.body": {"en": "Port must be a number.", "bs": "Port mora biti broj."},
    "msg.missing_fields.title": {"en": "Missing fields", "bs": "Nedostaju polja"},
    "msg.missing_fields.body": {
        "en": "Host, username and password are required.",
        "bs": "Host, korisničko ime i lozinka su obavezni.",
    },
    "msg.test_prompt.title": {"en": "Test email", "bs": "Test email"},
    "msg.test_prompt.body": {
        "en": "Send a test message to which address?",
        "bs": "Na koju adresu poslati test poruku?",
    },
    "msg.test_failed.title": {"en": "Test failed", "bs": "Test neuspješan"},
    "msg.test_sent.title": {"en": "Test sent", "bs": "Test poslan"},
    "msg.test_sent.body": {
        "en": "Test email sent to {to}.",
        "bs": "Test email poslan na {to}.",
    },

    # Auto-send result messages
    "msg.reminders.title": {"en": "Reminders", "bs": "Podsjetnici"},
    "msg.reminders.none": {
        "en": "No reminders need to be sent right now.",
        "bs": "Trenutno nema podsjetnika za slanje.",
    },
    "msg.reminders.sent_header": {
        "en": "Sent reminders to:",
        "bs": "Podsjetnici poslani:",
    },
    "msg.reminders.failed_header": {"en": "Failed:", "bs": "Neuspješno:"},
    "msg.email_not_set.title": {"en": "Email not set up", "bs": "Email nije podešen"},
    "msg.email_not_set.body": {
        "en": "Open Email Settings first and enter your SMTP details.",
        "bs": "Prvo otvorite Postavke e-pošte i unesite SMTP podatke.",
    },

    # ---------- Automation section ----------
    "auto.section": {"en": "Automation", "bs": "Automatizacija"},
    "auto.startup": {
        "en": "Start with Windows (run quietly in tray)",
        "bs": "Pokreni sa Windowsom (radi tiho u sistemskoj traci)",
    },
    "auto.daily": {
        "en": "Run a daily reminder check at",
        "bs": "Pokreni dnevnu provjeru podsjetnika u",
    },
    "auto.daily.note": {
        "en": "Reminders are sent even if the app window is closed. Your PC must be on at this time.",
        "bs": "Podsjetnici se šalju čak i kada je aplikacija zatvorena. Računar mora biti uključen u to vrijeme.",
    },
    "auto.error.title": {"en": "Automation error", "bs": "Greška automatizacije"},
    "auto.error.body": {
        "en": "Could not configure Windows automation:\n\n{error}",
        "bs": "Nije bilo moguće podesiti Windows automatizaciju:\n\n{error}",
    },

    # ---------- Tray icon menu ----------
    "tray.show": {"en": "Show window", "bs": "Prikaži prozor"},
    "tray.check_now": {"en": "Check reminders now", "bs": "Provjeri podsjetnike sada"},
    "tray.quit": {"en": "Quit", "bs": "Izađi"},
    "tray.tooltip": {"en": "Club Manager", "bs": "Club Manager"},

    # ---------- Email content ----------
    "email.subject_upcoming": {
        "en": "Membership renewal reminder ({club})",
        "bs": "Podsjetnik – obnova članarine ({club})",
    },
    "email.subject_overdue": {
        "en": "Membership has expired ({club})",
        "bs": "Podsjetnik – članarina je istekla ({club})",
    },
    "email.greeting": {"en": "Dear {name},", "bs": "Poštovani/Poštovana {name},"},
    "email.body_upcoming": {
        "en": ("This is a friendly reminder that your annual membership "
               "comes due for renewal on {due} – in {when} from today.\n\n"
               "Please renew your membership in time to continue enjoying "
               "all the benefits of our club."),
        "bs": ("Šaljemo Vam prijateljski podsjetnik da Vaša godišnja "
               "članarina dolazi na red za obnovu {due} – za {when} od "
               "danas.\n\n"
               "Molimo Vas da blagovremeno obnovite članarinu kako biste i "
               "dalje uživali sve pogodnosti našeg kluba."),
    },
    "email.body_overdue": {
        "en": ("This is a friendly reminder that your annual membership "
               "expired on {due} ({ago} ago).\n\n"
               "Please renew it as soon as possible to continue enjoying "
               "all the benefits of our club."),
        "bs": ("Šaljemo Vam prijateljski podsjetnik da je Vaša godišnja "
               "članarina istekla {due} (prije {ago}).\n\n"
               "Molimo Vas da je obnovite što prije kako biste i dalje "
               "uživali sve pogodnosti našeg kluba."),
    },
    "label.email_message": {"en": "Email Message", "bs": "Sadržaj emaila"},
    "label.email_upcoming": {"en": "Upcoming payment", "bs": "Predstojeća uplata"},
    "label.email_overdue": {"en": "Overdue payment", "bs": "Istekla uplata"},
    "label.email_placeholders": {
        "en": "Placeholders: {due} = due date  •  {when} = time phrase (upcoming)  •  {ago} = days overdue (overdue)  •  {name} = member name  •  {club} = club name",
        "bs": "Placeholders: {due} = datum uplate  •  {when} = vremenski izraz (predstojeće)  •  {ago} = dana zakašnjenja (isteklo)  •  {name} = ime člana  •  {club} = naziv kluba",
    },
    "email.thanks": {"en": "Thank you!", "bs": "Hvala Vam!"},
    "email.sign_off": {"en": "Kind regards,", "bs": "Srdačan pozdrav,"},

    # "in X" phrases used in body_upcoming → {when}
    "when.approx_1mo": {"en": "approximately 1 month", "bs": "otprilike mjesec dana"},
    "when.approx_2mo": {"en": "approximately 2 months", "bs": "otprilike dva mjeseca"},
    "when.approx_3mo": {"en": "approximately 3 months", "bs": "otprilike tri mjeseca"},
}
