# Run on Windows after: pip install -e '.[bundle]'
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot/../..")
python -m PyInstaller --clean --noconfirm --onedir --windowed --name MermaidDiagramStudio --paths src src/diagram_editor/main.py
Write-Host "Inspect dist/MermaidDiagramStudio and test on Windows before distributing."
