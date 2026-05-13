# Club Manager

A lightweight Windows desktop app for tracking yearly club memberships and sending automatic email reminders when a member's payment is due.

Built with Python + Tkinter. No internet connection required to run — all data stays on your PC.

---

## Features

- Add, edit and delete members with payment dates
- Colour-coded member list: overdue (red), due soon (yellow), OK (white)
- Automatic email reminders sent via Gmail, Outlook or any SMTP provider
- Customisable reminder email text with placeholders (see below)
- System tray icon — runs quietly in the background
- Start with Windows at login
- Daily scheduled reminder check via Windows Task Scheduler
- English / Bosnian UI (switchable at runtime)
- Single `.exe` build — no installation needed

---

## Running from source

### Requirements

- Python 3.10 or newer
- Windows (the automation features use `winreg` and `schtasks.exe`)

### Install dependencies

```
pip install pystray Pillow
```

> `pyinstaller` and `reportlab` are only needed if you want to build the `.exe` yourself (see below).

### Run

```
python main.py
```

The app creates `club.db` in the same folder on first run. That file holds all your member data and email settings — keep it backed up and **do not commit it to git** (it contains your SMTP password).

---

## Building the .exe

A PowerShell build script is included. It installs all build dependencies, regenerates the bundled PDF guides and produces a single `dist\ClubManager.exe`:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The resulting `.exe` is fully self-contained. Copy it to any Windows PC and it will create `club.db` next to itself on first launch.

---

## Setting up email (Gmail)

1. Open **Email Settings** inside the app.
2. Enter your club name, your Gmail address and select **Gmail** as the provider.
3. For the **App password** field — this is *not* your normal Gmail password. You need to generate a 16-character App Password:
   - Go to [myaccount.google.com](https://myaccount.google.com) → Security → App passwords
   - Create one named "Club Manager" and paste it into the app
4. Click **Send Test Email** to verify everything works before saving.

A step-by-step PDF guide (English and Bosnian) is bundled inside the app and opens when you click **"How do I get this password?"**.

---

## Customising the reminder email

Inside **Email Settings → Email Message** you can write your own reminder text. The default text is pre-filled as an example.

Use these placeholders anywhere in the message — they are replaced with real values when each email is sent:

| Placeholder | Replaced with | Example output |
|-------------|---------------|----------------|
| `{name}` | Member's full name | `Petar Petrović` |
| `{due}` | Payment due date | `11.06.2026.` |
| `{when}` | Time until due (upcoming emails) | `otprilike mjesec dana` |
| `{ago}` | How long overdue (overdue emails) | `3 dana` |
| `{club}` | Club name from settings | `Anels Club` |

**Upcoming payment example:**
```
Poštovani/Poštovana {name},

Šaljemo Vam podsjetnik da Vaša godišnja članarina dolazi na red za obnovu {due} – za {when} od danas.

Molimo Vas da blagovremeno obnovite članarinu.

Srdačan pozdrav,
{club}
```

**Overdue payment example:**
```
Dear {name},

This is a reminder that your membership expired on {due} ({ago} ago).

Please renew as soon as possible.

Kind regards,
{club}
```

---

## Windows automation

Both options are toggled inside **Email Settings → Automation**. Neither requires administrator rights.

| Feature | What it does |
|---------|-------------|
| **Start with Windows** | Launches the app silently in the system tray when you log in |
| **Daily reminder check** | Registers a Task Scheduler job that runs `ClubManager.exe --send-only` at the chosen time every day — reminders are sent even when the app window is closed |

---

## Command-line flags

These are used internally by the automation features but can also be run manually:

| Flag | Effect |
|------|--------|
| *(no flag)* | Opens the full GUI |
| `--tray` | Starts minimised to the system tray |
| `--send-only` | Sends any due reminders and exits immediately (no GUI) |

---

## Privacy

- All data (members, settings, SMTP password) is stored in `club.db` — a local SQLite file that never leaves your PC.
- The SMTP password is obfuscated in the database (base64). This protects against casual inspection but is not encryption — anyone with access to the file could decode it.
- `club.db` is excluded from git via `.gitignore`. Never commit it.

---

## Project structure

```
main.py          — GUI (tkinter), main window and dialogs
db.py            — SQLite layer (members + settings tables)
mailer.py        — Email composition and SMTP sending
i18n.py          — English / Bosnian string table
autorun.py       — Windows startup and Task Scheduler helpers
build_pdf.py     — Generates the bundled App Password PDF guides
build.ps1        — PyInstaller build script
assets/          — Icons and PDF guides bundled into the .exe
```

---

## License

MIT
