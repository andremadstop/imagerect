# TESTING.md — Manueller Test-Plan vor Release

> Diese Checkliste geht Andre manuell durch bevor eine Version als stabil
> freigegeben wird. Bei jedem Fail: Issue/Task anlegen und fixen.

## Voraussetzung

```bash
cd ~/Workspace/Code/imagerect
git pull
.venv/bin/pip install -e '.[dev,3d]'
.venv/bin/pre-commit run --all-files      # muss grün sein
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v   # alle grün
```

## Linux-Smoke (Workstation)

```bash
.venv/bin/python main.py
```

Checkliste:

- [ ] App startet ohne Error
- [ ] Dark Theme ist durchgängig (keine grauen Qt-Defaults)
- [ ] Toolbar zeigt Icons + Text (📷 📐 📦 …)
- [ ] Fenstergröße vernünftig (kein winziger Dialog)
- [ ] **Load Image** — JPG/PNG/TIFF lädt, wird angezeigt, Zoom+Pan gehen
- [ ] **Load DXF** — DXF lädt, Layer-Liste erscheint, Geometrie sichtbar
- [ ] **Layer toggeln** — Checkbox an/aus blendet Linien ein/aus
- [ ] **Marker-Skalierung** — Kontrollpunkt bleibt gleich groß beim Zoomen
- [ ] **Ctrl+Click** in Bild setzt Kontrollpunkt (NICHT plain click)
- [ ] **Ctrl+Click** in DXF setzt Referenzpunkt + snap auf Vertex
- [ ] **Plain Click** tut nichts bzw. wählt bestehenden Punkt aus
- [ ] **Mittelklick-Drag** pannt in beiden Viewern
- [ ] **Punkt-Tabelle** unten füllt sich, zeigt Koordinaten
- [ ] **4+ Punkte** → RMS wird angezeigt, Residualvektoren erscheinen
- [ ] **Punkt löschen** via Delete-Taste
- [ ] **Undo/Redo** (Ctrl+Z / Ctrl+Shift+Z)
- [ ] **Projekt speichern** → `.imagerect.json` Datei
- [ ] **Projekt laden** → Zustand wiederhergestellt
- [ ] **Lens Correction Dialog** öffnet, Presets dropdown befüllt
- [ ] **EXIF-Detection** — DJI-JPG zeigt "Detected: DJI ..."
- [ ] **Preset anwenden** — Bild wird sichtbar korrigiert
- [ ] **Image ROI** (✂) — Polygon auf Bild zeichnen, Fläche markiert
- [ ] **DXF ROI** (🔲) — Rechteck auf Plan ziehen, Bereich hervorgehoben
- [ ] **Project Panel** zeigt Maßstab/DPI/Pixelgröße, verlinkt
- [ ] **Export Preview** öffnet, zeigt entzerrtes Bild mit DXF-Overlay
- [ ] **Export** schreibt PNG und TIFF + JSON-Sidecar
- [ ] **BigTIFF-Export** funktioniert bei großem Canvas (>20k px)
- [ ] App beendet sauber (kein Segfault)

## Echt-Daten-Workflow (St. Georg Berlin)

Datenbasis:
- `tests/sample_data/2026_016_Maerkplan_StGeorg_Berlin.dwg`
- DWG → DXF konvertieren via CloudConvert (AutoCAD 2013 Format)
- `tests/sample_data/DJI_20260226143936_0003_V.JPG` (Orgel-Fassade)

Workflow:

- [ ] Foto laden
- [ ] Lens Correction anwenden (Preset: "DJI FC3582" oder entsprechend)
- [ ] DXF laden (St. Georg Grundriss)
- [ ] DXF ROI setzen auf den relevanten Fassadenabschnitt
- [ ] Mindestens 6 Kontrollpunktpaare setzen (Ecken, markante Punkte)
- [ ] RMS prüfen — sollte <5px sein bei sauberen Punkten
- [ ] Image ROI um den zu entzerrenden Bereich ziehen
- [ ] Maßstab im Project Panel auf 1:50, DPI 300 stellen
- [ ] Format TIFF, 16-bit, LZW-Kompression wählen
- [ ] Export Preview ansehen — DXF-Overlay passt?
- [ ] Export ausführen
- [ ] TIFF in GIMP/Photoshop öffnen — Maße und Schärfe prüfen
- [ ] JSON-Sidecar checken — Transform, Units, RMS eingetragen

## Windows-Installer (VM oder anderer PC)

Voraussetzung: GitHub Release mit Windows-Installer existiert.

- [ ] `ImageRect-x.x.x-Setup.exe` von GitHub Releases downloaden
- [ ] SmartScreen-Warnung akzeptieren ("Trotzdem ausführen")
- [ ] Installer läuft durch, zeigt deutsche UI
- [ ] Installation in `C:\Program Files\ImageRect\`
- [ ] Startmenü-Eintrag vorhanden
- [ ] Optional Desktop-Shortcut erstellt (falls angehakt)
- [ ] App startet per Startmenü
- [ ] Dark Theme wie auf Linux
- [ ] Icon in Taskbar sichtbar
- [ ] Load Image + Load DXF funktioniert
- [ ] Ctrl+Click setzt Punkt (Windows-Pfade ohne Encoding-Fehler)
- [ ] Lens Correction mit DJI-Preset
- [ ] Export läuft durch
- [ ] TIFF-Ausgabe öffnet sich in Windows Foto-App
- [ ] App deinstallieren via Windows-Einstellungen
- [ ] Nach Deinstallation: keine Reste in Program Files

## macOS-Binary (falls verfügbar)

- [ ] `.app` downloaden
- [ ] "Nicht verifizierter Entwickler" via Rechtsklick→Öffnen bypassen
- [ ] App startet
- [ ] Smoke-Workflow wie Linux
- [ ] HiDPI/Retina-Rendering ok

## Edge Cases

- [ ] **Riesiges Bild** (>50MP) lädt ohne Crash
- [ ] **Winziges Bild** (<100px) funktioniert
- [ ] **Leere DXF** (nur ein Layer, keine Segmente) wird behandelt
- [ ] **Korrupte DXF** zeigt Fehlermeldung statt Crash
- [ ] **DWG statt DXF** zeigt Hilfe-Dialog
- [ ] **<4 Punkte** → Export ist deaktiviert oder warnt klar
- [ ] **Kollineare Punkte** → Warnung wird angezeigt
- [ ] **Kontrollpunkt löschen** nach Lens-Correction funktioniert
- [ ] **Lens Correction rückgängig** → Punkte zurück in Original-Koordinaten
- [ ] **Export mit 100k+ px Canvas** — läuft durch (tile-basiert), kein OOM
- [ ] **Mosaik mit 2+ Bildern** → korrektes Stitching

## Release-Freigabe

Alle P0/P1-Checkboxen grün → v0.2.1 kann als stable taggen.
Einzelne P2-Bugs akzeptabel wenn dokumentiert in Release Notes.
