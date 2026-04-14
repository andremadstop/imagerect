# HANDOFF.md — Aktuelle Session-Situation

> Wird nach jeder größeren Session aktualisiert. Codex/Claude liest
> das als erstes wenn eine neue Session startet.

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
