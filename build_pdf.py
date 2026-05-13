"""Generate the Gmail App Password walkthrough PDFs (Bosnian + English).

Run from inside the ClubManager folder:
    python -m pip install reportlab
    python build_pdf.py

Output:
    assets/gmail_app_password_en.pdf
    assets/gmail_app_password_bs.pdf

Re-run any time the screenshots or caption text change.
``reportlab`` is a build-time dependency only — the running app does not
import it; it just opens the prebuilt PDF in the user's default viewer.
"""
from __future__ import annotations

import os

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
)


# ---- paths ----------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
STEPS_DIR = os.path.join(HERE, "assets", "gmail_steps")
OUT_DIR = os.path.join(HERE, "assets")

# ---- fonts (Arial bundles Latin Extended-A → Bosnian diacritics work) -----
_FONT_DIR = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("Arial",            os.path.join(_FONT_DIR, "arial.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Bold",       os.path.join(_FONT_DIR, "arialbd.ttf")))
pdfmetrics.registerFont(TTFont("Arial-Italic",     os.path.join(_FONT_DIR, "ariali.ttf")))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic", os.path.join(_FONT_DIR, "arialbi.ttf")))
registerFontFamily("Arial", normal="Arial", bold="Arial-Bold",
                   italic="Arial-Italic", boldItalic="Arial-BoldItalic")


# ---- layout ---------------------------------------------------------------
PAGE_W, PAGE_H = A4
MARGIN = 1.7 * cm
IMG_MAX_H = 12 * cm   # cap on image height per page

TITLE = ParagraphStyle("title", fontName="Arial-Bold", fontSize=22,
                       leading=26, spaceAfter=12)
STEP_HEADING = ParagraphStyle("step", fontName="Arial-Bold", fontSize=15,
                              leading=20, spaceAfter=6)
BODY = ParagraphStyle("body", fontName="Arial", fontSize=12,
                      leading=18, spaceAfter=8)
NOTE = ParagraphStyle("note", fontName="Arial", fontSize=10,
                      leading=14, textColor=HexColor("#5a4500"),
                      leftIndent=10, rightIndent=10,
                      backColor=HexColor("#fff3cd"),
                      borderColor=HexColor("#f0d57a"),
                      borderWidth=0.5, borderPadding=6,
                      spaceBefore=4, spaceAfter=4)


# ---- step list & assets ---------------------------------------------------
STEP_KEYS = ["step1", "step2", "step3", "step4", "step5", "step6"]
IMAGES = {
    "step1": "step1_account_home.png",
    "step2": "step2_security_off.png",
    "step3": "step3_security_on.png",
    "step4": "step4_apppass_empty.png",
    "step5": "step5_apppass_named.png",
    "step6": "step6_apppass_generated.png",
}


# ---- caption text (bilingual) --------------------------------------------
T = {
    "title": {
        "en": "How to get your Gmail App Password",
        "bs": "Kako dobiti App lozinku za Gmail",
    },
    "intro": {
        "en": ("This guide shows how to create a Gmail App Password — the "
               "16-character code Club Manager needs in order to send "
               "reminder emails on your behalf. The screenshots are from a "
               "Danish Google account, but the layout is identical in every "
               "language: look for the same icons in the same positions."),
        "bs": ("Ovaj vodič pokazuje kako kreirati Gmail App lozinku — "
               "16-znakovni kod koji Club Manager treba da bi mogao slati "
               "podsjetnike u Vaše ime. Slike su sa danskog Google naloga, "
               "ali izgled je identičan u svim jezicima: tražite iste "
               "ikonice na istim mjestima."),
    },
    "step_label": {"en": "Step", "bs": "Korak"},

    "step1_title": {
        "en": "Open your Google Account",
        "bs": "Otvorite svoj Google nalog",
    },
    "step1_body": {
        "en": ("Go to <b>myaccount.google.com</b> in your web browser and "
               "sign in if asked. You will see the dashboard with your "
               "name in the middle and a list of options on the left."),
        "bs": ("Posjetite <b>myaccount.google.com</b> u svom web "
               "pregledniku i prijavite se ako je potrebno. Vidjet ćete "
               "kontrolnu ploču sa Vašim imenom u sredini i listom opcija "
               "s lijeve strane."),
    },

    "step2_title": {
        "en": "Open the Security page",
        "bs": "Otvorite stranicu Sigurnost",
    },
    "step2_body": {
        "en": ("In the left sidebar, click <b>Security</b> (in this Danish "
               "example: <i>Sikkerhed og login</i>). Scroll down until you "
               "see the <b>2-Step Verification</b> row "
               "(<i>Totrinsverificering</i>)."),
        "bs": ("U lijevom meniju kliknite <b>Sigurnost</b> (na ovoj "
               "danskoj slici: <i>Sikkerhed og login</i>). Pomjerite se "
               "dolje dok ne vidite red <b>Verifikacija u dva koraka</b> "
               "(<i>Totrinsverificering</i>)."),
    },
    "step2_note": {
        "en": ("If it shows <b>Off</b> (<i>slået fra</i>), click on it and "
               "follow Google's setup — you will need your phone to receive "
               "a code. When it shows a green check, return here."),
        "bs": ("Ako pokazuje <b>Isključeno</b> (<i>slået fra</i>), kliknite "
               "na nju i pratite Googleove korake — trebat će Vam telefon "
               "za primanje koda. Kada se pojavi zelena kvačica, vratite se "
               "na ovaj vodič."),
    },

    "step3_title": {
        "en": "Confirm 2-Step Verification is On",
        "bs": "Potvrdite da je verifikacija uključena",
    },
    "step3_body": {
        "en": ("Once enabled, the row shows a green check and the words "
               "<b>On since…</b> (<i>Aktiveret siden…</i>). Only now can "
               "you continue to the App Password page."),
        "bs": ("Kada je uključena, red pokazuje zelenu kvačicu i tekst "
               "<b>Uključeno od…</b> (<i>Aktiveret siden…</i>). Tek sada "
               "možete nastaviti na stranicu App lozinki."),
    },

    "step4_title": {
        "en": "Open the App Passwords page",
        "bs": "Otvorite stranicu App lozinki",
    },
    "step4_body": {
        "en": ("In your browser's address bar, type "
               "<b>myaccount.google.com/apppasswords</b> and press Enter. "
               "Google may ask for your account password again — that is "
               "normal. You will land on a page with one empty field "
               "labeled <b>App name</b> (<i>Appens navn</i>)."),
        "bs": ("U adresnoj traci preglednika upišite "
               "<b>myaccount.google.com/apppasswords</b> i pritisnite "
               "Enter. Google može tražiti da ponovo unesete svoju "
               "lozinku — to je uobičajeno. Stići ćete na stranicu sa "
               "jednim praznim poljem <b>Ime aplikacije</b> "
               "(<i>Appens navn</i>)."),
    },

    "step5_title": {
        "en": "Name the App Password",
        "bs": "Imenujte App lozinku",
    },
    "step5_body": {
        "en": ("Type a name you will recognise — for example "
               "<b>Club Manager</b> — into the field, then click the blue "
               "<b>Create</b> button (<i>Opret</i>) in the bottom right."),
        "bs": ("Upišite ime koje ćete prepoznati — na primjer "
               "<b>Club Manager</b> — u to polje, zatim kliknite plavo "
               "dugme <b>Kreiraj</b> (<i>Opret</i>) u donjem desnom uglu."),
    },

    "step6_title": {
        "en": "Copy the 16-character password",
        "bs": "Kopirajte 16-znakovnu lozinku",
    },
    "step6_body": {
        "en": ("Google shows a popup with a password made of four groups "
               "of four letters. Select it with your mouse, copy it, then "
               "paste it into the <b>SMTP password</b> field in Club "
               "Manager's Email Settings."),
        "bs": ("Google prikazuje prozor sa lozinkom od četiri grupe po "
               "četiri slova. Označite je mišem, kopirajte i nalijepite u "
               "polje <b>SMTP lozinka</b> u Postavkama e-pošte u Club "
               "Manageru."),
    },
    "step6_note": {
        "en": ("Google only shows this password <b>once</b>. After you "
               "close the popup it cannot be viewed again. If you lose "
               "it, just create a new App Password the same way — it "
               "takes 30 seconds."),
        "bs": ("Google ovu lozinku prikazuje samo <b>jednom</b>. Nakon "
               "što zatvorite prozor, više se ne može vidjeti. Ako je "
               "izgubite, jednostavno kreirajte novu na isti način — "
               "potrebno je 30 sekundi."),
    },
}


def t(lang: str, key: str) -> str:
    return T.get(key, {}).get(lang) or T.get(key, {}).get("en") or key


def has_key(key: str) -> bool:
    return key in T


def scaled_image(path: str, max_w: float = PAGE_W - 2 * MARGIN,
                 max_h: float = IMG_MAX_H) -> Image:
    ir = ImageReader(path)
    iw, ih = ir.getSize()
    aspect = ih / iw
    w, h = max_w, max_w * aspect
    if h > max_h:
        h, w = max_h, max_h / aspect
    return Image(path, width=w, height=h)


def build_pdf(lang: str, out_path: str) -> None:
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=t(lang, "title"), author="Club Manager",
    )
    elements: list = []

    elements.append(Paragraph(t(lang, "title"), TITLE))
    elements.append(Paragraph(t(lang, "intro"), BODY))
    elements.append(PageBreak())

    for n, key in enumerate(STEP_KEYS, start=1):
        heading = f"{t(lang, 'step_label')} {n}: {t(lang, f'{key}_title')}"
        elements.append(Paragraph(heading, STEP_HEADING))
        elements.append(Paragraph(t(lang, f"{key}_body"), BODY))
        if has_key(f"{key}_note"):
            elements.append(Paragraph(t(lang, f"{key}_note"), NOTE))
        elements.append(Spacer(1, 6))
        elements.append(scaled_image(os.path.join(STEPS_DIR, IMAGES[key])))
        if n < len(STEP_KEYS):
            elements.append(PageBreak())

    doc.build(elements)
    print(f"  wrote {out_path}")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print("Generating PDFs:")
    for lang in ("en", "bs"):
        out = os.path.join(OUT_DIR, f"gmail_app_password_{lang}.pdf")
        build_pdf(lang, out)
    print("Done.")


if __name__ == "__main__":
    main()
