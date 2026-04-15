# ImageRect

[![CI](https://github.com/andremadstop/imagerect/actions/workflows/ci.yml/badge.svg)](https://github.com/andremadstop/imagerect/actions/workflows/ci.yml)
[![Release Build](https://github.com/andremadstop/imagerect/actions/workflows/release.yml/badge.svg)](https://github.com/andremadstop/imagerect/actions/workflows/release.yml)

ImageRect is a local-first Linux desktop prototype for manual, metric image rectification against 2D and planar 3D references. The current `main` scope covers DXF-based rectification plus Phase-2 support for E57 point clouds and OBJ meshes via a user-defined working plane, lens correction, ROI-aware export, tiled large-image output, multi-image mosaics, GPS pose metadata, and a headless CLI for saved projects.

![Screenshot](docs/screenshot.png)

## Current scope

- Load PNG/JPG/TIFF/PPM source images
- Load DXF references with layer visibility toggles
- Load E57 point clouds and OBJ meshes as 3D references
- Define a working plane from 3 picks or an automatic plane fit
- Pick corresponding image and reference points manually
- Apply lens correction presets or custom camera metadata before rectification
- Compute image-to-reference homography with RMS error and residual vectors
- Draw an image clip polygon and a DXF region of interest for export bounds
- Preview exports with DXF/control-point overlays before writing to disk
- Export TIFF, BigTIFF, PNG, or JPEG at 8/16/32-bit depth
- Stream tiled TIFF export for very large canvases
- Combine multiple source images into a shared mosaic with optional feather blending
- Extract GPS/EXIF pose hints and write camera pose metadata JSON
- Save/load project JSON
- Validate saved projects and re-export them headlessly via `imagerect-cli`
- Inspect image, DXF, E57, and OBJ files from the command line
- Export rectified imagery plus metadata JSON
- Undo/redo point edits, delete points, and reorder point rows

DWG is not a hard dependency in the MVP. Convert DWG to DXF first if needed.

## Recently added on `main`

- Lens correction workflow with preset matching and EXIF-assisted camera selection
- Image clip polygons and DXF region-of-interest export bounds
- Export preview dialog with overlay toggles and live size estimates
- 8-bit, 16-bit, and 32-bit output with TIFF, BigTIFF, PNG, and JPEG targets
- Streaming tiled TIFF export for very large canvases
- Multi-image project support with shared-reference mosaic export
- GPS/EXIF pose extraction, rough pre-alignment markers, and camera pose metadata output
- Headless CLI commands for `export`, `validate`, and `inspect`
- Input hardening for oversized images, malformed reference files, and unsafe relative project paths

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .[dev]
```

Optional 3D support:

```bash
.venv/bin/pip install -e '.[dev,3d]'
```

`open3d` is used when available for E57 downsampling and automatic plane fitting. If it is unavailable on your platform, OBJ loading and the manual 3-point plane workflow still work, and plane fitting falls back to an SVD-based estimate.

## Installation

**Windows:**

- Download `ImageRect-x.x.x-Setup.exe` from [GitHub Releases](https://github.com/andremadstop/imagerect/releases).
- Run the installer. It installs to Program Files and creates a Start Menu entry.
- If you prefer a portable build, download `ImageRect.exe` instead.
- The release bundle also contains `ImageRect-cli.exe` for headless export and validation.

**Linux:**

- Download `ImageRect` from GitHub Releases.
- Run `chmod +x ImageRect && ./ImageRect`.
- The release bundle also contains `ImageRect-cli` for headless workflows.
- Optional: copy [installer/imagerect.desktop](/home/andre/Workspace/Code/imagerect/installer/imagerect.desktop) to `~/.local/share/applications/`.

**macOS:**

- Download `ImageRect.app` from GitHub Releases.
- Move it to Applications.
- For the first launch on an unsigned build, right-click and choose `Open`.

**From source:**

```bash
git clone https://github.com/andremadstop/imagerect.git
cd imagerect
python -m venv .venv
.venv/bin/pip install -e '.[dev,3d]'
.venv/bin/python main.py
```

## Run

```bash
.venv/bin/python main.py
```

You can also preload assets:

```bash
.venv/bin/python main.py --image path/to/photo.jpg --reference path/to/reference.dxf
.venv/bin/python main.py --image path/to/photo.jpg --reference path/to/reference.obj
```

CLI workflows:

```bash
.venv/bin/imagerect-cli validate path/to/project.imagerect.json
.venv/bin/imagerect-cli export path/to/project.imagerect.json --output build/out --format png
.venv/bin/imagerect-cli inspect tests/sample_data/synthetic_reference.dxf
```

## Workflow

### DXF workflow

1. Load an image.
2. Load a DXF reference.
3. Click a point in the image.
4. Click the matching point in the reference.
5. Repeat until at least four valid pairs exist.
6. Inspect RMS and residual vectors.
7. Export the rectified image.

The export dialog lets you define pixel size, output format, interpolation, and optional clipping to the control-point hull.

### Lens correction workflow

1. Load the source image.
2. Open `Lens Correction`.
3. Start from the detected preset or enter a custom focal length and sensor width.
4. Compare the before/after preview and apply the correction.
5. Place or refine image control points on the corrected source image.

Lens correction is stored per image in the project file, so mosaic projects can mix different camera profiles.

### Mosaic workflow

1. Load the first image and place its control points against the shared reference.
2. Load additional images with the same reference still open.
3. Switch active images from the `Images` list in the project panel.
4. Solve at least four valid pairs per image.
5. Export once to compose all solved images into one shared reference canvas.

The Phase-1 mosaic compositor uses last-written wins by default and can optionally feather seams with a configurable blend radius in pixels.

### Large-image export (>100k px)

- The export engine predicts output size and canvas dimensions before writing files.
- TIFF and BigTIFF exports switch to tiled streaming for very large canvases, avoiding full-frame warps in RAM.
- Multi-layer TIFF exports can include the rectified image, DXF overlay, control-point layer, and clip-mask layer.
- BigTIFF is enabled automatically when the predicted file size crosses the 4 GB threshold, or explicitly when selected.

### GPS pose output

- Image loading extracts GPS latitude/longitude/altitude, heading, and timestamps from EXIF and drone XMP metadata when available.
- DXF references with embedded `EPSG:<code>` metadata expose rough camera markers in the 2D reference viewer.
- Export metadata JSON includes the rectified canvas bounds plus per-image GPS hints and camera pose output derived from homography decomposition when intrinsics are known.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+I` | Load source image |
| `Ctrl+D` | Load DXF reference |
| `Ctrl+Shift+D` | Load 3D reference |
| `Ctrl+E` | Export rectified image or mosaic |
| `Ctrl+P` | Toggle project settings panel |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` / `Ctrl+Y` | Redo |
| `Delete` | Delete selected point |
| `Ctrl+Up` / `Ctrl+Down` | Reorder selected point |
| `Ctrl+Click` or `Shift+Click` | Place a control point in the active viewer |
| `Middle-drag` | Pan the active viewer |
| `Mouse wheel` | Zoom the active viewer |

### 3D workflow

1. Load an image.
2. Load an E57 point cloud or OBJ mesh.
3. Define the working plane from three picks or use `3D -> Plane Auto`.
4. Click a point in the image.
5. Click the matching point on the 3D geometry.
6. Repeat until at least four valid pairs exist.
7. Inspect RMS and export the rectified image.

The 3D viewer supports orbit with right-drag, pan with middle-drag, zoom with the mouse wheel, and displays the working plane as a semi-transparent overlay.

## Quick Start

1. Start `imagerect` or run `.venv/bin/python main.py`.
2. Load a source image.
3. Load either a DXF, E57, or OBJ reference.
4. For 3D references, define the working plane first.
5. Add at least four matching point pairs.
6. Inspect RMS and residual warnings.
7. Export PNG or TIFF plus metadata JSON.

## Supported Formats

| Category | Formats | Notes |
| --- | --- | --- |
| Images in | PNG, JPG, JPEG, TIFF, BMP, PPM | Loaded through OpenCV |
| 2D references | DXF | First-class support |
| 2D references via conversion | DWG | Convert to DXF first |
| 3D references | E57, OBJ | E57 via `pye57`, OBJ via `trimesh` |
| 3D references later | FBX | Not in the MVP |
| Project files | `.imagerect.json` | Save/load reproducible sessions |
| Exports | PNG, TIFF, JSON | Rectified image plus metadata |

## Smoke test

The repository contains a synthetic Phase-1 verification path that instantiates the Qt window offscreen, generates a synthetic source image, solves the homography, and exports the result.

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --smoke-test
```

## Troubleshooting

ImageRect writes rotating log files locally for bug diagnosis:

- Linux: `~/.imagerect/logs/imagerect.log`
- macOS: `~/Library/Logs/ImageRect/imagerect.log`
- Windows: `%LOCALAPPDATA%\ImageRect\logs\imagerect.log`

The GUI also provides:

- `Hilfe -> Log-Ordner öffnen`
- `Hilfe -> Diagnose-Paket exportieren...`

The diagnose ZIP contains `system_info.json`, the current rotated logs, and the
active project JSON when the project has already been saved to disk.

When reporting a bug, attach the diagnose package and include a short note
describing the exact workflow that triggered the issue.

## Tests

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest
```

CLI quick checks:

```bash
.venv/bin/imagerect-cli --help
.venv/bin/imagerect-cli validate tests/golden/golden_project.imagerect.json
.venv/bin/imagerect-cli export tests/golden/golden_project.imagerect.json --output build/cli-smoke --format png
```

## Synthetic sample data

The file [tests/sample_data/synthetic_reference.dxf](/home/andre/Workspace/Code/imagerect/tests/sample_data/synthetic_reference.dxf:1) provides a small metric DXF fixture used by the smoke test and unit tests.

## Contributing

Contributions should stay focused on the local-first rectification workflow. Keep changes small, add or extend tests with each behavior change, and run the local quality toolchain before opening a pull request.

## Documentation

- [User Guide & Tutorial](docs/USER_GUIDE.md) - Full reference manual and step-by-step tutorial.

## License

ImageRect is released under the MIT License. See [LICENSE](/home/andre/Workspace/Code/imagerect/LICENSE).
