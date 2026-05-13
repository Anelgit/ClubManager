# Build a single-file Windows .exe for Club Manager.
# Run from inside the ClubManager folder:
#   powershell -ExecutionPolicy Bypass -File .\build.ps1

$ErrorActionPreference = "Stop"

Write-Host "==> Installing build dependencies (if needed)..."
python -m pip install --upgrade pip pyinstaller reportlab pystray Pillow

# Regenerate the Gmail App Password PDFs if the source assets exist.
if (Test-Path -Path ".\build_pdf.py") {
    Write-Host "==> Regenerating Gmail App Password PDFs..."
    python build_pdf.py
}

Write-Host "==> Building ClubManager.exe ..."
# --add-data uses ';' as src;dest separator on Windows (':' on Unix).
python -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name "ClubManager" `
    --add-data "assets;assets" `
    --collect-submodules "pystray" `
    --collect-submodules "PIL" `
    main.py

Write-Host ""
Write-Host "Done. Your .exe is at: dist\ClubManager.exe"
Write-Host "Just copy that file anywhere - it will create club.db next to itself."
