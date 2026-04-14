# ImageRect — Promo-Assets

> Alles rund um die Bekanntmachung der App. Nicht von Codex pflegen
> lassen — Promo ist kreativ/visuell.

## Struktur

- `channels.md` — Wo bekanntmachen, in welcher Reihenfolge (Launch-Plan)
- `screenshots/` — Hochauflösende App-Screenshots (PNG, sortiert
  nach Workflow-Schritt)
- `gifs/` — kurze Animationen (Punkte setzen, Preview, Export)
- `video/` — längere Demos (Skripte + Aufnahmen)
- `posts/` — vorbereitete Texte für jeden Kanal (Show-HN, Reddit-Posts,
  Mastodon-Thread, LinkedIn)
- `landing/` — Assets für eine Landing-Page (Hero-Bild, Icons,
  Feature-Grafiken)

## Minimal-Set für v0.2.1-Launch

1. 4-6 Screenshots des kompletten Workflows (siehe `screenshots/`)
2. Ein 10-20s GIF als Hero im README
3. README-Pitch-Absatz (ein Satz Positionierung)
4. Kanalspezifische Posts (siehe `channels.md` + `posts/`)

## Positionierung (Arbeitstitel)

> "Open-Source-Desktop-App für metrische Bildentzerrung. Fassadenfotos,
> Grundrisse, archäologische Aufnahmen — von Foto plus Referenzgeometrie
> (DXF/E57/OBJ) zu maßstäblichem Bild. Python, PySide6, MIT-Lizenz."

Abgrenzung:
- **Nicht** Metashape/RealityCapture (kein Mesh, keine Photogrammetrie
  aus hunderten Bildern)
- **Nicht** Photoshop Perspective Warp (kein Maßstab, kein DXF)
- **Schon**: Einzelbild-Entzerrung mit vorhandener CAD-Referenz,
  Open Source, lokal, skriptbar
