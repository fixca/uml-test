#!/usr/bin/env bash
# Run on macOS after: pip install -e '.[bundle]'
set -euo pipefail
cd "$(dirname "$0")/../.."
python -m PyInstaller --clean --noconfirm --windowed --onedir --name MermaidDiagramStudio --paths src src/diagram_editor/main.py
echo 'Inspect dist/MermaidDiagramStudio.app and sign/notarize before distributing.'
