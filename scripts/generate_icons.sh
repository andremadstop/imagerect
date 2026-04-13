#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p assets/generated

render_png() {
    local size="$1"
    local output="assets/generated/icon-${size}.png"

    if command -v inkscape >/dev/null 2>&1; then
        inkscape assets/icon.svg \
            --export-type=png \
            --export-filename="${output}" \
            --export-width="${size}" \
            --export-height="${size}"
        return
    fi

    if command -v magick >/dev/null 2>&1; then
        magick -background none assets/icon.svg -resize "${size}x${size}" "${output}"
        return
    fi

    if command -v convert >/dev/null 2>&1; then
        convert -background none assets/icon.svg -resize "${size}x${size}" "${output}"
        return
    fi

    echo "Need one of: inkscape, magick, or convert" >&2
    exit 1
}

for size in 16 32 48 64 128 256 512; do
    render_png "${size}"
done

if command -v magick >/dev/null 2>&1; then
    magick assets/generated/icon-{16,32,48,64,128,256}.png assets/icon.ico
elif command -v convert >/dev/null 2>&1; then
    convert assets/generated/icon-{16,32,48,64,128,256}.png assets/icon.ico
else
    echo "Need ImageMagick (magick/convert) to build assets/icon.ico" >&2
    exit 1
fi

if command -v png2icns >/dev/null 2>&1; then
    png2icns assets/icon.icns \
        assets/generated/icon-16.png \
        assets/generated/icon-32.png \
        assets/generated/icon-128.png \
        assets/generated/icon-256.png \
        assets/generated/icon-512.png
else
    python - <<'PY'
from pathlib import Path
import struct

chunks = []
for chunk_type, filename in [
    ("icp4", "assets/generated/icon-16.png"),
    ("icp5", "assets/generated/icon-32.png"),
    ("icp6", "assets/generated/icon-64.png"),
    ("ic07", "assets/generated/icon-128.png"),
    ("ic08", "assets/generated/icon-256.png"),
    ("ic09", "assets/generated/icon-512.png"),
]:
    data = Path(filename).read_bytes()
    chunks.append(chunk_type.encode("ascii") + struct.pack(">I", len(data) + 8) + data)

payload = b"".join(chunks)
Path("assets/icon.icns").write_bytes(b"icns" + struct.pack(">I", len(payload) + 8) + payload)
PY
fi

cp assets/generated/icon-256.png assets/icon.png

echo "Icons generated in assets/"
