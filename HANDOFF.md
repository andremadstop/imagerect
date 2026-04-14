# HANDOFF.md — Aktuelle Session-Situation

> Wird nach jeder größeren Session aktualisiert. Codex/Claude liest
> das als erstes wenn eine neue Session startet.

## Stand 2026-04-14 tief nachts — Tasks 012/013/010 abgeschlossen, CI grün

### Was in dieser Session dazukam

- Andre hat die verbliebenen Draft-Tasks **012**, **013** und **010**
  explizit freigegeben (`"mach alles autonom fertig"`); damit sind jetzt
  alle von Claude vorbereiteten Restaufgaben umgesetzt
- **Task 012 — Security Hardening** abgeschlossen:
  500-MP-Limit für Bilder, defensive DXF/E57/OBJ-Fehlerpfade,
  Pfad-Traversal-Schutz für relative Projektpfade, defensiver
  Diagnose-Output sowie neue CI-Sicherheitsgates mit `bandit`,
  `pip-audit`, Dependabot und CodeQL
- **Task 013 — UI-Flow-Tests** abgeschlossen:
  `pytest-qt`-Fixture plus Flows für Modifier-Click, Punktlöschung,
  Projekt-Roundtrip, Export-Gating und Action-Descriptions
- **Task 010 — CLI-Foundation** abgeschlossen:
  neues `imagerect-cli` mit `export`, `validate` und `inspect`, dazu
  Release-/Installer-Anbindung und synchronisierte User-Doku
- Die zugehörigen Commits auf `main` sind jetzt:
  `ac688df` (`fix: harden project inputs and cover ui regressions`),
  `8767bc1` (`feat: add imagerect-cli headless workflows`),
  `c4dd238` (`test: fix security hardening regex lint`)
- Der erste Push dieser Session hatte genau **einen** CI-Fail:
  `ruff` verlangte in `tests/test_security_hardening.py` einen raw
  Regex-String. Das wurde direkt mit `c4dd238` nachgezogen; kein
  Laufzeitfehler, nur Lint-Korrektur

### Was grün ist

- `PRE_COMMIT_HOME=/tmp/pre-commit .venv/bin/pre-commit run --all-files`
- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v`
- `QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --smoke-test`
- `.venv/bin/imagerect-cli --help`
- `.venv/bin/imagerect-cli validate tests/golden/golden_project.imagerect.json`
- `.venv/bin/imagerect-cli export tests/golden/golden_project.imagerect.json --output build/cli-smoke --format png`
- `.venv/bin/imagerect-cli inspect tests/sample_data/synthetic_reference.dxf`
- GitHub CI `24412316782`
- GitHub CodeQL `24412316785`
- Vor dem Lint-Fix war GitHub CodeQL auf dem ersten Push bereits grün:
  `24412200612`; die erste CI `24412200581` ist nur wegen des Regex-Lints
  rot geworden und danach sauber nachgezogen

### Nächster Zustand

- Es ist **kein** von Claude vorbereiteter Rest-Task mehr offen;
  `010`, `011`, `012`, `013`, `014` und `015` sind abgearbeitet
- Nächster sinnvoller Schritt ist jetzt Andres manueller
  Workstation-Test: GUI-Flow für 014/015 und CLI-Smoke für 010
- Offene Folgehinweise außerhalb des jetzigen Scopes:
  GitHub-Actions-Annotation zur Node-20-Deprecation,
  CodeQL-Action-v3-Deprecation sowie die automatisch erzeugten
  Dependabot-PRs aus der neuen Konfiguration

## Stand 2026-04-14 spät nachts — Task 011 CI-Fix abgeschlossen

### Was in dieser Session dazukam

- Der erste Task-011-Push war lokal grün, aber GitHub CI schlug fehl,
  weil `tests/golden/golden_project.imagerect.json` durch
  `*.imagerect.json` in `.gitignore` nicht versioniert war
- `.gitignore` bekam eine gezielte Ausnahme für genau diese
  committete Golden-Project-Fixture
- Der fehlende Test-Artefakt-Commit ist jetzt auf `main`:
  `3e9ca6e` (`test: track golden project fixture`)

### Was grün ist

- `.venv/bin/pre-commit run --all-files`
- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v`
- `QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --smoke-test`
- GitHub CI `24405956267`

### Nächster Zustand

- Task 011 ist jetzt vollständig verifiziert, lokal und in GitHub CI
- Kein weiterer autonom vorbereiteter Task offen; nächster sinnvoller
  Schritt ist wieder Andres Priorisierung oder manueller UI-Check für
  die Änderungen aus 014/015

## Stand 2026-04-14 spät nachts — Task 011 auf direkte Freigabe umgesetzt

### Was in dieser Session dazukam

- Andre hat den früheren STOP nach Task 015 **explizit aufgehoben**
  (`"mach einfach weiter"`), deshalb wurde der freigegebene
  Leerlauf-Task 011 direkt nachgezogen
- **Task 011 — Property-based + Golden-File Tests** umgesetzt:
  `hypothesis` als Dev-Dependency ergänzt, neues
  `tests/test_transform_properties.py`, neues
  `tests/test_export_golden.py`, Golden-Fixtures unter `tests/golden/`
  und Regenerationsskript `scripts/regenerate_golden.py`
- Property-Tests decken Homographie-Invarianten, Invertierbarkeit,
  Rang und degenerierte Eingaben über Warnung/Fehler ab
- Golden-Tests decken den Export deterministisch gegen committete
  TIFF/JPEG-Artefakte und normalisierte Metadaten ab

### Was grün ist

- `.venv/bin/pre-commit run --all-files`
- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v`
- `QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --smoke-test`

### Nächster Zustand

- Kein weiterer autonomer Scope-Sprung vorbereitet
- Sinnvoller nächster Schritt ist jetzt wieder Andres manuelle Prüfung
  der UI-Fixes aus 014/015; Task 011 war reine Test-Härtung ohne
  User-facing Änderung

## Stand 2026-04-14 nachts — Task 015 abgeschlossen, jetzt STOP

### Was in dieser Session fertig wurde

- **Task 015 — DXF-Viewer State Preservation** abgeschlossen in
  4 Commits auf `main`:
  `13ac851` (`fix: preserve dxf view state across refreshes`),
  `74416b1` (`fix: auto-zoom the first dxf roi`),
  `0b32d5a` (`feat: add dxf view fit actions`),
  `436e415` (`docs: note the harmless wayland mouse-grab warning`)
- `Reference2DViewer.set_reference()` behält den aktuellen Transform
  bei identischem DXF-Objekt und fit-t nur noch bei echtem
  Referenz-Wechsel
- Erste sinnvolle DXF-ROI zoomt genau einmal in die Region; danach
  bleibt die Ansicht stabil
- Neues Menü **Ansicht** mit `Ctrl+0` (An DXF anpassen),
  `Ctrl+Shift+0` (An ROI anpassen) und `Ctrl+1` (Bild anpassen)
- `grabMouse` kommt laut Repo-Grep aktuell **nicht** aus ImageRect-Code;
  die Wayland-Warnung ist deshalb als bekanntes Qt-Gotcha in
  `AGENTS.md` dokumentiert

### Was grün ist

- `.venv/bin/pre-commit run --all-files`
- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v`
- `QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --smoke-test`

### Nächster Zustand

- **STOP bis Andre manuell testet**
- Andre soll jetzt Lens-Dialog + DXF-Navigation interaktiv prüfen:
  Viewport bleibt nach Punktsetzung, ROI zoomt einmalig, Menü-Shortcuts
  greifen, Lens-Preview/Apply bleibt sichtbar
- Erst nach Andres Freigabe weiter zu anderen Tasks; laut Handoff keine
  eigenmächtige Fortsetzung zu 010/011/012/013/016

## Stand 2026-04-14 spätabends — Task 014 abgeschlossen, Task 015 als Nächstes

### Was in dieser Session fertig wurde

- **Task 014 — Lens Correction Preview + Apply Fix** abgeschlossen in
  3 Commits auf `main`:
  `a332a8e` (`fix: update lens preview when parameters change`),
  `97426a4` (`fix: keep lens apply visible in the image viewer`),
  `1a5d9a3` (`test: cover the full lens apply workflow`)
- Lens-Dialog reagiert jetzt debounced auf Parameter-Änderungen der
  Spinboxes und Preset-Übernahmen
- Der `ImageViewer` behält seinen Ausschnitt über reine Bild-Refreshes
  hinweg, statt bei Lens-Apply sofort wieder auf Fit-to-View zu springen
- Neue Regressionstests decken Spinbox-Preview, sichtbaren Apply-Pfad
  und den vollständigen Dialog-zu-Viewer-Flow ab

### Was grün ist

- `.venv/bin/pre-commit run --all-files`
- `QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v`
- `QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --smoke-test`

### Wichtige Einschränkung

- **Manueller GUI-Check steht weiter auf Andres Seite aus**:
  Lens-Dialog live durchklicken und auf echtem Bildmaterial visuell
  bestätigen. Dieser Session-Stand ist technisch verifiziert, aber
  nicht per interaktivem Desktop-Test abgesegnet.

### Nächster Schritt

1. **Task 015 — DXF-Viewer State Preservation** starten
2. Nach 015: pushen, CI prüfen, dann laut Handoff **STOP** bis Andre
   manuell testet

## Stand 2026-04-14 abends — bgis/Peiler-Integration beachten

> **WICHTIG FÜR CODEX**: ImageRect ist public, MIT, allgemein.
> bgis-Adoption ist ein Use-Case, kein Constraint. Das Repo bleibt
> lokal-first und allgemein verständlich, ohne bgis-spezifische
> Credentials, Hostnames oder Kundendaten.

### Welche Files Peiler ingestiert

Manifest im bgis-copilot-Repo:
`https://github.com/andremadstop/bgis-copilot/blob/master/backend/seeds/imagerect.yaml`

- `README.md` — Projektübersicht + Feature-Liste
- `AGENTS.md` — Projekt-Struktur + Konventionen
- `HANDOFF.md` — aktueller Entwicklungsstand
- `ROADMAP.md` — geplante Phasen
- `TESTING.md` — Test-/QA-Konzept
- `docs/**/*.md` — User-Dokumentation

`CODEX-TASK-*.md` werden aktuell **nicht** ingestiert. Das sind lokale
interne Task-Notizen und bleiben außerhalb des public repo.

### Konsequenzen für Codex

- **HANDOFF.md nach jeder Session aktualisieren** — das ist Peilers
  "Was hat Andre gerade gemacht"-Quelle
- **README.md Feature-Liste im gleichen Commit wie neue Features
  aktualisieren**
- **ROADMAP.md bei Richtungswechsel im gleichen Arbeitsgang anpassen**
- **Breaking Changes erzwingen Doku-Update im gleichen Commit**
- **Commit-Messages verständlich formulieren**, damit Timeline-Einträge
  für bgis-Anwender lesbar bleiben

### Heute vs. später

- Heute: Peiler pullt `main` täglich per Cron und ingestiert geänderte
  Dateien SHA-idempotent neu. Kein Action-Item für Codex.
- Später möglich, aber jetzt nicht bauen:
  `.github/workflows/notify-peiler.yml` für on-push Webhook-Notify
- Später möglich, aber jetzt nicht bauen:
  Issue-Template `bgis-request.md`, falls Peiler User-Wünsche direkt
  als Issues anlegt

### Nicht tun

- Keine bgis-Daten, Screenshots, Logfiles oder Credentials committen
- Keinen bgis-spezifischen Code in ImageRect einbauen
- Keine Sonder-Branches "für bgis" anlegen; `imagerect` bleibt sauberes
  public project

## Stand 2026-04-14 nachmittags — 3-Tage-Autonom-Run für Codex

> **WICHTIG FÜR CODEX**: Andre ist die nächsten ~3 Tage nur sporadisch
> erreichbar. Du arbeitest autonom. Halte dich strikt an die
> Reihenfolge + Leitplanken unten. Bei Unklarheiten: Zwischenstand
> in HANDOFF.md dokumentieren und auf Rückmeldung warten — NICHT raten.

### Arbeits-Reihenfolge (verbindlich)

1. **Task 014 — Lens Preview + Apply Fix** (v0.2.1-Blocker aus User-Testing)
   Datei: `CODEX-TASK-014-lens-preview-apply-fix.md`
2. **Task 015 — DXF-Viewer State Preservation** (v0.2.1-Blocker, blockiert Testing)
   Datei: `CODEX-TASK-015-dxf-viewer-state-preservation.md`
3. **Nach 014 + 015 gepusht und CI grün**: STOP. Andre muss manuell
   testen bevor weitere Tasks starten. Kein eigenmächtiges Weitergehen
   zu Task 010/011/012/013 — die haben andere Reihenfolge-Constraints.
4. Falls du 014 + 015 in <1 Tag durch hast und idle bist:
   **Task 011 (Property + Golden Tests)** ist freigegeben als
   Sinnvoller-Leerlauf — keine User-facing Änderung, nur Test-Coverage.
   Task 012/013 NICHT starten (CI-Workflow-Änderungen wollen
   Abstimmung, UI-Tests wollen stabile UI nach 014+015).

### Leitplanken (nicht verletzen)

- **Scope-Drift vermeiden**: Jeder Task bleibt im dokumentierten Scope.
  Keine Bonus-Refactorings, keine "while I'm here"-Cleanups. Wenn etwas
  Aufmerksamkeit braucht, in `INBOX.md` vermerken und weitergehen.
- **Scope-Guards** (aus AGENTS.md) weiterhin aktiv:
  `core/transform.py` und `core/reference2d.py` NICHT anfassen ohne
  expliziten Auftrag. Task 014/015 erfordern das auch nicht.
- **Jeder Task endet mit manueller Verifikation** — lens-apply
  sichtbar, viewport bleibt nach Punkt. Der Commit-Message muss die
  Verifikation explizit erwähnen.
- **CI muss nach JEDEM Commit grün sein**, nicht erst am Task-Ende.
  Falls ein Commit CI kaputtmacht: stopp, fix im nächsten Commit, nicht
  weiterbauen auf rotem Stand.
- **Keine Release-Tags** (v0.2.1 etc.) ohne Andre. Du pushst auf main,
  Tagging ist User-Entscheidung.
- **Keine neuen Runtime-Dependencies** in Task 014/015/011. Falls du
  eine für notwendig hältst: HANDOFF-Eintrag + stoppen.
- **Task-Drafts 010, 012, 013, 016** sind TABU bis Andre freigibt.
- **Bei Bug-Discovery während 014/015**: neuen Bug in INBOX.md
  aufnehmen, nicht im laufenden Task mitfixen (Scope-Drift).

### Kontext zu den Test-Bugs (vom Linux-Smoke-Test)

- User startete App (`.venv/bin/python main.py`)
- Qt-Warnung mehrfach im stderr: "This plugin supports grabbing the
  mouse only for popup windows" — wird in Task 015 Commit 4 adressiert
- Lens-Dialog: Profile durchschalten zeigt keine Live-Preview-Änderung,
  OK/Apply schließt Dialog ohne sichtbaren Effekt im ImageViewer
- DXF-Viewer: Zoom in Region → Punkt setzen → Viewport springt zurück
  zu Fit-to-View. Kein Auto-Zoom auf ROI, kein View-Lock.

Die Root-Cause-Analyse ist in den Task-Files bereits drin — du kannst
direkt loslegen.

### Blockiert auf Andre (nach 014 + 015)

- Manueller Linux-Smoke-Test mit den Fixes
- Windows-Installer-Test (wenn er Zeit findet)
- Echt-Daten-Workflow (DJI-Fotos + St. Georg DXF)

### Tagesrhythmus (Empfehlung für autonomen Betrieb)

- Tag 1: Task 014 (3 Commits + Verifikation)
- Tag 2: Task 015 (4 Commits + Verifikation)
- Tag 3: Task 011 wenn idle, sonst warten auf Andre. Kein Weitergehen
  zu anderen Tasks.

### Notebook

NotebookLM-Notebook `601131dd-c8da-4099-8efd-63c02f9f1161` hat den
aktuellen Stand mit 15 Sources. Task-Files 014/015 sind noch nicht
im Notebook — nach Abschluss wird Andre beim nächsten Sync nachladen.

---

## Stand 2026-04-14 morgens — Task 009 abgeschlossen

### Was in dieser Session dazukam

- **Task 009 vollständig abgeschlossen** in 3 Commits auf `main`:
  `c89da3d` (rotierende Logfiles), `859eaeb` (Diagnose-Paket im Hilfe-Menü),
  `8169b88` (README/TESTING-Doku)
- **CI auf `main` grün** für alle drei Task-009-Commits, zuletzt Run
  `24387929687` (`docs: diagnose package in TESTING.md + README.md`)
- Neue Debugging-Infrastruktur jetzt in der App:
  Logfiles unter `~/.imagerect/logs/`, Menü
  `Hilfe -> Log-Ordner öffnen`, Menü
  `Hilfe -> Diagnose-Paket exportieren...`

### Reihenfolge jetzt

1. **Andre führt `TESTING.md` Linux-Smoke durch** inklusive neuem Diagnose-Paket
2. **Andre testet Windows-Installer** aus GitHub Release `v0.2.0`
3. **Andre macht Echt-Daten-Workflow** (DJI-Fotos + St. Georg DXF)
4. **Gefundene Bugs** werden als neue `CODEX-TASK-NNN-*.md` festgehalten
5. Danach: Docs/Screenshots vervollständigen und **v0.2.1** vorbereiten
6. **Task 010 bleibt DRAFT** und startet erst nach v0.2.1-Release

### Blockiert auf User-Aktion

- Linux-Smoke, Windows-Installer-Test und Echt-Daten-Workflow liegen jetzt
  beim User
- Ohne diese manuellen Ergebnisse sollte Task 010 nicht gestartet werden

---

## Stand 2026-04-14 spätabends — Tasks 009 + 010 vorbereitet

### Was in dieser Session dazukam

- **ROADMAP.md** erweitert: P1.5 Debugging-Infrastruktur (Task 009),
  v0.3.0 CLI-Foundation-Block, paralleler Doku-/Promo-Workstream
- **CODEX-TASK-009-log-export.md** — bereit für Codex, nach Task 008
  starten. 3 Commits: Logging-Setup → Diagnose-Paket → Docs
- **CODEX-TASK-010-cli-foundation.md** — Skizze, DRAFT, nicht starten
  bevor v0.2.1 released ist
- **docs/** + **promo/** Verzeichnisse angelegt mit README und
  `promo/channels.md` (Launch-Plan Tier 1/2/3)

### Reihenfolge jetzt

1. ✅ Codex hat Task 008 fertig, CI grün, v0.2.0 auf abfac8d retaggt,
   Release-Build inkl. Windows-Installer durch
2. **Andre testet Windows-Installer** (Gating zu v0.2.1)
3. Codex Task 009 (Log-Export) — kann parallel zu Windows-Test starten
4. Docs + Screenshots füllen → v0.2.1 Release
5. Task 011-013 (Property-Tests, Security, UI-Tests) vor öffentlicher Promo
6. Tier 1 Promo (Show HN, Reddit, Mastodon) — siehe promo/channels.md
7. Danach Task 010 (CLI-Foundation, v0.3.0)

### Task-Pipeline nach Task 008

- **Task 009** (log-export) — ready for Codex, nach Andres Freigabe
- **Task 010** (cli-foundation) — DRAFT, nach v0.2.1
- **Task 011** (property + golden tests) — DRAFT, vor Promo
- **Task 012** (security hardening) — DRAFT, vor Promo
- **Task 013** (ui-flow tests) — DRAFT, nach 012

### NotebookLM

Notebook `601131dd-c8da-4099-8efd-63c02f9f1161` mit 11 initialen
Sources befüllt (README, AGENTS, ROADMAP, TESTING, HANDOFF, docs/promo,
Tasks 008-010). Neue Task-Drafts 011-013 können bei Bedarf nachgeladen
werden.

---

## Stand 2026-04-14 Abend — Session-Ende, Handover an Codex

### Was diese Session gebaut hat

- Task 007 durch Codex autonom erledigt (10 Commits, 22 neue Tests,
  v0.2.0 getaggt)
- Task 008 von Codex angefangen (Installer-Fix gepusht, Lens-Fix lokal,
  CI libEGL-Fix offen)
- Handover-Dokumentation angelegt: AGENTS.md, ROADMAP.md, TESTING.md,
  HANDOFF.md
- Memory-Eintrag project_imagerect.md + feedback_claude_codex_split.md
- NotebookLM-Notebook erstellt (noch ohne Sources)

### Claude pausiert — Codex übernimmt

Claude (Andre's Session-Tokens) nahe Wochenlimit. Die nächsten Tage
arbeitet Andre direkt mit Codex weiter anhand dieser 4 Dokumente:
- AGENTS.md (Konstitution)
- ROADMAP.md (Priorisierung)
- TESTING.md (manueller Testplan)
- HANDOFF.md (dieser Stand)

## Stand davor — Task 007 abgeschlossen

### Was läuft / ist offen

- **Task 008** ist Codex-side **in Arbeit** (CI libEGL + Lens-Remap + v0.2.0 Retag)
- Lokal uncommittete Änderungen in `core/lens.py` und `ui/main_window.py`
  (Lens-Remap-Fix, wird in Task 008 Commit 1 gepackt)
- `.codex` Datei ist untracked, bleibt drin (User-Config)

### Was grün ist

- 39 Pytest-Tests (lokal)
- Pre-commit Hooks (ruff, mypy, whitespace, yaml)
- main.py startet, Smoke-Test läuft durch
- 12 Commits auf main, v0.2.0 getaggt (aber CI rot wegen libEGL)
- GitHub Repo public: https://github.com/andremadstop/imagerect

### Was rot ist

- **CI-Workflow** auf GitHub — ImportError libEGL.so.1 beim pytest
- **Release-Build v0.2.0** — scheitert am gleichen Problem + evtl. macOS
- Windows-Installer wurde nie erfolgreich gebaut

### Nächster konkreter Schritt

1. Codex Task 008 fertig durchlaufen lassen
2. Wenn gepusht: `gh run list --limit 3` — CI muss grün sein
3. Falls immer noch rot: weitere apt-Libs nachlegen (siehe Task 008
   "iterate apt-get list")
4. Wenn Release-Build grün: Windows-Installer aus GitHub Releases
   downloaden, auf Windows-Maschine installieren, Smoke-Test machen
   (siehe TESTING.md "Windows-Installer")

### Blockiert auf User-Aktion

- Windows-Testing — Andre braucht Windows-VM oder physischen PC
- Echt-Daten-Workflow — Andre muss DWG→DXF konvertieren (CloudConvert),
  dann TESTING.md "Echt-Daten-Workflow" durchgehen
- Memory-Limit — Claude (nicht Codex) nähert sich Wochenlimit;
  Codex übernimmt die nächsten Tage alleine

### Was Codex wissen muss

- **AGENTS.md** lesen vor jeder Session
- **ROADMAP.md** für Priorisierung
- **TESTING.md** als Referenz was User testen wird
- Bei neuen Tasks: CODEX-TASK-NNN-Format, landet im Projektroot
- Bei echten Problemen die User-Input brauchen: in HANDOFF.md unter
  "Blockiert auf User-Aktion" vermerken und mit Andre sprechen

### Zuletzt verwendete Kommandos

```bash
# Standard-Dev-Loop
cd ~/Workspace/Code/imagerect
.venv/bin/pre-commit run --all-files
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v
QT_QPA_PLATFORM=offscreen .venv/bin/python main.py --smoke-test
.venv/bin/python main.py    # GUI-Launch für manuelles Testen

# Git/GitHub
git status
gh run list --limit 5
gh run view <id> --log-failed

# Build
./scripts/build.sh          # lokaler PyInstaller-Build
```

### Offene Entscheidungen

Keine. Alles im Scope von Task 008 ist klar beschrieben.

### Letzte Commits

```
f4e4f68 test: comprehensive coverage + docs for v0.2.0
0dab6c9 feat: mosaic workflow + GPS pose export
70ee83c feat: export engine — streaming tiled export for huge images
bbc2aad feat: export engine — BigTIFF, bit depths, compression
f237c51 feat: export preview with DXF overlay and quality info
7542161 feat: project settings panel (scale, DPI, units, output params)
b3a22a9 feat: lens correction with camera presets + EXIF auto-detect
70652c6 feat: ROI — image clip polygon + DXF region selection
fd72947 feat: modifier-click for point placement (Metashape-style)
8c2642a fix: UX — marker scaling, hide 3D actions in 2D, status hints
b300a43 fix: restore installer build and export typing (ongoing)
```

---

## Update-Regeln für diese Datei

- Nach jeder abgeschlossenen Session: "Stand"-Header aktualisieren
- "Was läuft / ist offen" — ganz knapp (3-5 Zeilen)
- "Nächster konkreter Schritt" — genau einer, nicht mehrere
- "Blockiert auf User-Aktion" — nur wenn wirklich blockiert
- Alte HANDOFF-Stände NICHT löschen, sondern unter `---` nach unten schieben
  (Archiv/Historie)
