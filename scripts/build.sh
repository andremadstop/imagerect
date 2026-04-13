#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f assets/icon.png ] || [ ! -f assets/icon.ico ] || [ ! -f assets/icon.icns ]; then
    ./scripts/generate_icons.sh
fi

python -m pip install pyinstaller
pyinstaller imagerect.spec --clean --noconfirm
echo "Build complete: dist/ImageRect"
