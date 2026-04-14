# AGENTS.md — Projekt-Konstitution für Codex

> Diese Datei ist die zentrale Referenz für alle AI-Agenten die an
> ImageRect arbeiten. Vor jeder Session lesen.

## Was ist ImageRect

Open-Source-Desktop-App für metrische Bildentzerrung. Nutzer markiert
Kontrollpunkte auf einem Foto und einer Referenzgeometrie (DXF, E57,
OBJ), App berechnet Homographie, exportiert maßstäbliches Bild.

Repo: https://github.com/andremadstop/imagerect
Sprache: Python 3.11+
Stack: PySide6, OpenCV, numpy, ezdxf, Open3D (optional), pye57, trimesh, Pillow, tifffile
Lizenz: MIT

## Architektur

```
core/              — Business-Logik, kein Qt
  project.py         — Projektmodell, JSON-Persistierung
  image.py           — Bild-I/O
  reference2d.py     — DXF-Parser
  reference3d.py     — E57/OBJ + Working Plane + 3D→2D
  transform.py       — Homographie-Solver
  export.py          — Warp + Canvas-Berechnung
  lens.py            — Verzeichnungskorrektur
  writers/           — TIFF/PNG/JPEG Writer
  pose.py            — Kamera-Pose-Dekomposition (GPS)

ui/                — Qt-Widgets, kein Business
  main_window.py     — Hauptfenster, Orchestrierung
  image_viewer.py    — Bild-Canvas
  reference2d_viewer.py  — DXF-Canvas
  reference3d_viewer.py  — 3D-Viewer (Qt-nativ, QPainter)
  point_table.py     — Kontrollpunkt-Tabelle
  project_panel.py   — Maßstab/DPI/Output-Einstellungen
  lens_dialog.py     — Lens-Correction-Dialog
  preview_dialog.py  — Export-Vorschau
  export_dialog.py   — (Legacy, wird durch project_panel ersetzt)
  theme.py           — Zentrales Dark-Theme + QSS

tests/             — pytest-basiert
main.py            — Entry Point
assets/            — App-Icon (SVG + generierte ICO/ICNS/PNG)
installer/         — Inno Setup Script für Windows
scripts/           — Build-Helfer
```

## Quality Gates — MUSS vor jedem Commit grün sein

```bash
cd ~/Workspace/Code/imagerect
.venv/bin/pre-commit run --all-files        # ruff + mypy + hooks
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v   # alle Tests grün
QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --smoke-test   # E2E-Smoke
```

Wenn ein Gate fehlschlägt: **nicht committen**. Root cause finden, fixen,
dann commit. Niemals `--no-verify` nutzen.

## Commit-Regeln

- **Ein logischer Change pro Commit.** Keine Mischcommits.
- **Commit-Messages auf Englisch** (Projekt ist international).
- **Conventional Commits** Format:
  - `feat: <beschreibung>` — neues Feature
  - `fix: <beschreibung>` — Bugfix
  - `test: <beschreibung>` — Tests hinzufügen
  - `docs: <beschreibung>` — Doku
  - `refactor: <beschreibung>` — Umstrukturierung ohne Feature-Change
  - `chore: <beschreibung>` — Wartung (Deps, CI-Config)
- **Nach jedem Commit pushen** wenn möglich, damit CI läuft.
- **Keine Co-Author-Tags** in Commit-Messages einfügen.

## Scope-Guards — NICHT anfassen ohne expliziten Auftrag

Diese Module sind stabil und werden nur auf explizite Anweisung geändert:
- `core/transform.py` — Homographie-Solver, mathematisch verifiziert
- `core/reference2d.py` — DXF-Parser, funktioniert für alle bisherigen Testdaten

Diese Dateien werden NIE automatisch geändert:
- `.codex` (User-Config)
- Alle Files in `tests/sample_data/` außer `synthetic_reference.dxf`

## Autonom vs. Rückfrage

### Autonom entscheiden
- Implementation eines klar beschriebenen Tasks (CODEX-TASK-*.md)
- Wahl zwischen äquivalenten Implementierungsvarianten
- Bugfixes mit klarer Root Cause
- Refactoring zur Lint/Type-Compliance
- Test-Ergänzungen die bestehende Funktionalität abdecken

### Immer fragen
- Neue Abhängigkeiten hinzufügen die nicht im Task stehen
- Bestehende Tests löschen oder Assertions ändern
- Scope erweitern über das im Task dokumentierte hinaus
- UI-Layout-Änderungen die User-Workflow betreffen
- Release-Tags löschen oder force-pushen
- Git History umschreiben (rebase, amend auf gepushten Commits)

## User-Kommunikation

- **Sprache: Deutsch** (User-Präferenz, CLAUDE.md-Regel)
- Knapp und faktisch, keine Floskeln
- Status-Reports: Was wurde gemacht, was ist grün, was ist blockiert
- Bei Fehlern: Root Cause + Fix-Vorschlag, nicht nur Error-Log
- Tool-Outputs kurz zusammenfassen, nicht 1:1 wiedergeben

## Task-File-Format

Neue Tasks landen als `CODEX-TASK-NNN-<kurzname>.md` im Projektroot.
Struktur:

```markdown
# Codex Task NNN — <Titel>

Context: <1-2 Absätze was vorher passiert ist>

Working directory: ~/Workspace/Code/imagerect/
Virtual env: .venv/
Tests: QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v
Pre-commit: .venv/bin/pre-commit run --all-files

## Phase A — <Name>
Commit: "<type>: <message>"

<Implementation details>

## Phase B — <Name>
...

## Constraints
- <Liste harter Regeln>
```

Tasks werden von mir (Andre) oder Claude geschrieben. Codex führt sie aus.

## Bekannte Konstanten & Gotchas

- **CI libEGL**: Ubuntu-Runner brauchen `libegl1 libxkbcommon0 libxcb-*`
  apt-Packages bevor PySide6 importiert werden kann.
- **DWG**: Nicht unterstützt. User muss extern zu DXF konvertieren
  (CloudConvert, FreeCAD). Dialog zeigt Hinweis.
- **offscreen QT**: Pytest und Smoke-Test laufen mit
  `QT_QPA_PLATFORM=offscreen`, sonst crashen sie in Headless-Umgebungen.
- **Pre-commit Hooks**: Liegen in `.pre-commit-config.yaml`, installiert
  via `.venv/bin/pre-commit install` — bei frisch geklontem Repo
  erneut ausführen.
- **tests/sample_data**: Echte DWG und JPG nicht committen (sind in
  `.gitignore`). Nur `synthetic_reference.dxf` ist getrackt.
- **Windows-Installer**: Nutzt Inno Setup via `installer/imagerect.iss`.
  Wird nur im GitHub Actions Release-Build gebaut, nicht lokal.

## Release-Prozess

1. Alle Tests grün auf main
2. Version in `pyproject.toml` bumpen
3. Tag: `git tag -a vX.Y.Z -m "<release notes kurz>"`
4. Push: `git push origin main --tags`
5. GitHub Actions `release.yml` triggert automatisch
6. Baut Linux/macOS/Windows-Binaries + Windows-Installer
7. Erstellt GitHub Release mit allen Artefakten
8. User testet Download-Install, gibt grünes Licht

## Memory

Bei größeren Änderungen an der Konstitution: Backlog-Eintrag
in `~/ObsidianVaults/Personal/Ops/backlog/BACKLOG.md` (append-only).

## Referenzen

- `ROADMAP.md` — Priorisierte Arbeitsreihenfolge
- `TESTING.md` — User-Test-Plan vor Release
- `HANDOFF.md` — Aktuelle Session-Situation
- `README.md` — User-facing Dokumentation
- `CODEX-TASK-*.md` — Einzelaufträge (History + Pending)
