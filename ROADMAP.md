# ROADMAP.md — Priorisierte Arbeitsreihenfolge

> Was nach dem aktuellen Stand (v0.2.0 getaggt) als nächstes ansteht.
> Ganz oben = als nächstes. Nach unten = später.

## Sofort (v0.2.1 Stabilisierung)

### P0 — Blocker für nutzbares Release
1. **Task 008 fertig** — CI libEGL, Lens-Fix committen, v0.2.0 retaggen
2. **CI muss grün sein** auf main — keine roten Builds in GitHub
3. **Release-Build muss Windows-Installer erzeugen** — als Artefakt
   downloadbar in GitHub Releases

### P1 — User-Testing vor erstem echten Release
4. **Linux-Smoke** — User (Andre) geht `TESTING.md` Linux-Checkliste durch
5. **Windows-Install** — User downloadet `ImageRect-x.x.x-Setup.exe`,
   installiert auf Windows-Maschine, startet, macht Smoke-Workflow
6. **Echt-Daten-Test** — User mit DJI-Fassadenfotos + DWG→DXF von
   St. Georg Berlin, kompletter Workflow bis Export
7. **Alle gefundenen Bugs** → neue Task-Files, fixen

### P1.5 — Debugging-Infrastruktur (ermöglicht sinnvolle Bug-Reports)
8. **Task 009 — Log-Export** — rotierende Logfiles in `~/.imagerect/logs/`,
   Menüpunkt "Hilfe → Diagnose-Paket exportieren" (Logs + Projekt-JSON +
   System-Info als ZIP). Zwischenschritt bis volle CLI. Siehe
   `CODEX-TASK-009-log-export.md`.

### P2 — Politur vor v1.0
9. **Nach Tests:** Bugs konsolidieren, retestgen bis stabil
10. **README.md** mit Screenshot updaten wenn App stabil aussieht
11. **GitHub Release v0.2.1** mit vollständigen Release Notes

## Mittelfristig (v0.3.0)

### Qualitäts- und Sicherheits-Hardening (Vorbereitung für externe User)

Sobald v0.2.1 released ist, lohnen sich diese Investments bevor das
Projekt ernsthaft beworben wird (Show HN, Reddit, FOSSGIS) — denn dann
kommen echte User mit echten Files, die möglicherweise malformed sind.

- **Task 011** — Property-based Tests (Hypothesis) für Homographie-Solver,
  Golden-File-Regression für Export-Pipeline
- **Task 012** — Security-Hardening: Decompression-Bomb-Schutz,
  DXF/E57-Parser-Härtung, Pfad-Traversal-Prävention in Projekt-Loader,
  `bandit` + `pip-audit` + Dependabot + CodeQL in CI
- **Task 013** — pytest-qt für UI-Flow-Tests (Modifier-Click,
  Projekt-Roundtrip, Lens-Dialog, Menu-Accessibility)

### CLI-Foundation — Zielzustand volle CLI-Bedienbarkeit

Kern ist bereits Qt-frei (`core/` ohne Qt-Imports) — CLI kann sich
sauber draufsetzen. Eigene Task-Serie ab `CODEX-TASK-010-cli-foundation.md`.

**Zielzustand**: `imagerect <subcommand> [flags]` deckt alle nicht-interaktiven
Operationen ab (Export, Batch, Validate, Inspect). GUI bleibt Erstwahl für
Kontrollpunkt-Setzung — CLI für Re-Export, CI-Integration, Batch-Jobs.

**Inkrementeller Ausbau** (nicht alles in einem Task):
1. `imagerect export <project.imagerect.json>` — headless Re-Export eines
   gespeicherten Projekts mit allen Einstellungen aus der JSON
2. `imagerect validate <project.imagerect.json>` — Schema/Pfad-Check ohne Export
3. `imagerect inspect <image|dxf|e57>` — Metadata-Dump (EXIF, DXF-Layer, etc.)
4. `imagerect batch <verzeichnis>` — mehrere Projekte sequenziell
5. `imagerect rectify` — vollständiger interaktionsfreier Flow für bekannte
   Fixture-Szenarien (Regression-Tests, CI-Golden-Files)

Tech: `typer` (CLI-Framework), Entry Point in `pyproject.toml` → `imagerect`.

### Weitere Kandidaten (Entscheidung nach v0.2.1-Feedback, 2-3 auswählen)

- **Auto-Feature-Detection** für Kontrollpunkte (SIFT/ORB-Matching
  als Vorschlag, User bestätigt)
- **GPS-Pre-Alignment-Verbesserung** — EXIF+XMP-Parsing, erweiterte
  Kamera-Posen-Rekonstruktion
- **Lens-Profile-Datenbank** aus lensfun importieren (offline)
- **DXF-Export** — entzerrte Bilder als georeferenzierter Raster
  zurück in DXF
- **Batch-Processing** — mehrere Bilder automatisch gegen gleiche
  Referenz entzerren (überschneidet sich mit CLI batch)
- **Projekt-Templates** — "Fassade 1:50 300dpi", "Grundriss 1:100 150dpi"
- **Kollaborations-Export** — Projekt-ZIP inkl. aller Assets für Teams
- **Histogramm/Tonwertkorrektur** im Bild-Viewer
- **Undo-Grenzen** konfigurierbar (aktuell unbegrenzt, kann RAM fressen)

## Langfristig (v0.4.0+)

- **3D-Ortho-Surface-Projection** — für gekrümmte Fassaden, echte
  Mesh-basierte Entzerrung (kein Plane-Fit mehr)
- **Vollständige Photogrammetrie-Pipeline** — Mehrbild-Triangulation,
  Bundle Adjustment (wenn Scope wächst)
- **Plugin-System** — dritte können Custom-Reader/Writer einklinken
- **Web-Version** — headless Core als Library, Browser-UI optional
  (wird aber Python/WASM-Thema)

## Bewusst NICHT geplant

- **Cloud-Features** — App bleibt local-first
- **Accounts/Auth** — kein User-Management
- **Proprietäre Formate** (PSD, PSB) — TIFF deckt alles ab
  (Entscheidung aus Session 2026-04-13)
- **Code Signing** — Projekt bleibt Open Source, User akzeptiert
  SmartScreen-Warning
- **DWG-nativer Import** — LibreDWG zu unreif, extern konvertieren
  bleibt einfacher

## Paralleler Workstream — Doku & Promo

Nicht Codex-Aufgabe (kreativ/visuell). Wird mit Claude oder Andre direkt
bearbeitet. Verzeichnisse: `docs/` (User-Handbuch, Tutorials, Screenshots)
und `promo/` (Landing-Page-Assets, GIF-Demos, Posts, README-Hero).

**Doku-Minimum vor v0.2.1-Release**:
- `docs/user-guide.md` — Installation, erster Workflow, Export-Settings
- `docs/troubleshooting.md` — typische Fehler + Diagnose-Paket nutzen
  (sobald Task 009 durch ist)
- `docs/workflows/fassade.md` — Schritt-für-Schritt mit St. Georg
  Beispiel-Daten

**Promo-Minimum vor v0.2.1-Release**:
- `promo/screenshots/` — 4-6 Screenshots des fertigen Workflows
- `promo/hero.gif` — 10-20s GIF: Punkte setzen → Export
- README.md mit Hero-Bild und einem Satz-Pitch
- Optional: GitHub Topics setzen (`photogrammetry`, `dxf`, `rectification`)

**Spätere Ausbaustufen** (nach v0.2.1):
- Landing-Page (Astro/Plain-HTML) unter Subdomain von `andrestiebitz.de`
- Demo-Video (3-5 Min, Echt-Daten-Walkthrough)
- Blog-Post zum Projekt auf `andrestiebitz-site`
- Cross-Posting: r/Photogrammetry, r/GIS, HN Show HN, Mastodon

## Entscheidungs-Prinzipien

Bei neuen Feature-Anfragen prüfen:
1. **Passt es zum Kern** (metrische Bildentzerrung)? Wenn nicht → ablehnen
2. **Bringt es einem echten User-Workflow was?** Nicht spekulativ bauen
3. **Kann man es in <1 Woche vernünftig umsetzen?** Wenn nicht → splitten
4. **Macht es bestehenden Code komplizierter?** Dann Kosten-Nutzen prüfen
