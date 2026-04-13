# ImageRect

[![CI](https://github.com/andremadstop/imagerect/actions/workflows/ci.yml/badge.svg)](https://github.com/andremadstop/imagerect/actions/workflows/ci.yml)
[![Release Build](https://github.com/andremadstop/imagerect/actions/workflows/release.yml/badge.svg)](https://github.com/andremadstop/imagerect/actions/workflows/release.yml)

ImageRect is a local-first Linux desktop prototype for manual, metric image rectification against 2D and planar 3D references. The current MVP covers DXF-based rectification plus Phase-2 support for E57 point clouds and OBJ meshes via a user-defined working plane.

![Screenshot](docs/screenshot.png)

## Current scope

- Load PNG/JPG/TIFF/PPM source images
- Load DXF references with layer visibility toggles
- Load E57 point clouds and OBJ meshes as 3D references
- Define a working plane from 3 picks or an automatic plane fit
- Pick corresponding image and reference points manually
- Compute image-to-reference homography with RMS error and residual vectors
- Save/load project JSON
- Export rectified PNG/TIFF plus metadata JSON
- Undo/redo point edits, delete points, and reorder point rows

DWG is not a hard dependency in the MVP. Convert DWG to DXF first if needed.

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

## Install From Release Binary

1. Download the latest archive for your platform from the GitHub Releases page.
2. Extract the archive.
3. Launch `ImageRect` on Linux/macOS or `ImageRect.exe` on Windows.

Release binaries are intended for quick evaluation. Building from source remains the most reliable way to get optional 3D extras.

## Run

```bash
.venv/bin/python main.py
```

You can also preload assets:

```bash
.venv/bin/python main.py --image path/to/photo.jpg --reference path/to/reference.dxf
.venv/bin/python main.py --image path/to/photo.jpg --reference path/to/reference.obj
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

## Tests

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest
```

## Synthetic sample data

The file [tests/sample_data/synthetic_reference.dxf](/home/andre/Workspace/Code/imagerect/tests/sample_data/synthetic_reference.dxf:1) provides a small metric DXF fixture used by the smoke test and unit tests.

## Contributing

Contributions should stay focused on the local-first rectification workflow. Keep changes small, add or extend tests with each behavior change, and run the local quality toolchain before opening a pull request.

## License

ImageRect is released under the MIT License. See [LICENSE](/home/andre/Workspace/Code/imagerect/LICENSE).
