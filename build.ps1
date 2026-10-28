# Gera o executável portátil (Windows): dist\CofreSenhas.exe
#
#     powershell -ExecutionPolicy Bypass -File build.ps1
#
# O .exe não precisa de Python instalado. Copie-o para o pendrive; o cofre
# fica na pasta "cofre_dados" criada ao lado dele no primeiro uso.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

uv sync --group build
uv run --group build pyinstaller gui.py `
    --name CofreSenhas `
    --onefile `
    --windowed `
    --collect-data customtkinter `
    --noconfirm `
    --clean

Write-Host "`npronto: dist\CofreSenhas.exe"
