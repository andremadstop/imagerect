# Promo-Kanäle — Wo bekanntmachen

> Strukturiert nach Tier. Tier 1 zuerst, Tier 2 nachdem v0.2.1 bewiesen
> hat dass nichts crasht, Tier 3 nach Feedback aus Tier 1+2.

## Tier 1 — Launch-Tag (v0.2.1 stable + Windows-Installer funktioniert)

### Show HN
- Titel: "Show HN: ImageRect — metric image rectification against CAD
  references (Python, MIT)"
- Link: GitHub-Repo
- Body: 2-3 Absätze Problem/Lösung, ein GIF, Hinweis auf Open Source
- Bestes Timing: Dienstag-Donnerstag, 8-10 Uhr Pacific = 17-19 Uhr DE
- **Achtung**: nur einmal möglich, Qualität zählt — erst wenn Doku +
  Screenshots stehen

### Reddit (Hauptkanäle — dort sitzt das Zielpublikum)
- **r/Photogrammetry** (48k) — Kern-Community, sehr relevant
- **r/GIS** (260k) — Grundrisse/Luftbilder, Überschneidung
- **r/surveying** (18k) — deutschsprachig? siehe r/Vermessung
- **r/Architecture** (2M) — Fassadendokumentation
- **r/Archaeology** (700k) — Fundstellenfotografie-Entzerrung
  (historisch größte Community für dieses Tooling)
- **r/selfhosted** + **r/opensource** — generischer Open-Source-Launch

Regeln: Flair setzen, als "I made this"-Post, keine Spam-Cross-Posts
(erst einer, dann Reaktion sehen, dann nächster Subreddit mit anderem
Text).

### Mastodon
- Thread mit 5-7 Toots, erster mit Video/GIF
- Hashtags: `#photogrammetry #opensource #gis #fossgis #architecture
  #surveying`
- Handle-Boosts: @osgeo, @opensourcegis, @fossgis, relevante
  Photogrammetrie-Accounts

### Hacker News (falls Show HN nicht greift)
- Normaler Post mit Blog-Artikel zu "warum ich das gebaut habe"

## Tier 2 — Community-Einbettung (Woche 2-4)

### Deutschsprachige GIS/Vermessungs-Communities
- **FOSSGIS e.V.** — Mailingliste, Forum, Konferenz-Einreichung
  https://fossgis.de — sehr passend für Andre als Deutscher,
  Open-Source-Fokus, GIS-Nähe
- **DVW** (Deutscher Verein für Vermessungswesen) — regionale
  Gruppen, Zeitschrift "zfv"
- **OSM-Community DE** — osm-forum.de, Telegram-Gruppen
- **heise Forum / golem.de Leserzuschriften** — News-Tipp einreichen
  (Open-Source-Launch ist ein kleiner News-Hook)

### Architektur/Bauforschung (Fassadenfotografie-Winkel)
- **OSArch** (osarch.org) — Open Source Architecture Community,
  sehr aktiv, IfcOpenShell/BlenderBIM-Umfeld
- **BlenderBIM Slack** — Tool-nahe Community
- **TU-Architekturfakultäten** — direkte Mails an Lehrstühle für
  Bauforschung/Bauaufnahme (TU Berlin, TU München, Bauhaus Weimar,
  HTW Berlin)
- **Bundesingenieurkammer / Architektenkammer** regional — Newsletter

### Archäologie (historisch größtes Tooling-Publikum für
Fotoentzerrung gegen Grundrisse)
- **CAA** (Computer Applications in Archaeology) — Mailingliste, Konferenz
- **Archaeology StackExchange**
- **r/Archaeology** und Academia.edu-Profile von digitalen Archäologen
- **Landesdenkmalpflege-Ämter** — direkter Tool-Pitch an IT-Referenten
  (Bauaufnahme, Steinliste)

### Python/Open-Source-Plumbing
- **PyPI** — Paket veröffentlichen wenn v0.2.1 stabil (`pip install imagerect`)
- **conda-forge** — später, wenn PyPI durch ist
- **awesome-listen**: awesome-photogrammetry, awesome-gis,
  awesome-python, awesome-archaeology — Pull Requests mit
  ImageRect-Eintrag
- **AlternativeTo.net** — Eintrag als Alternative zu Metashape
  (Single-Image-Rectification-Aspekt), RealityCapture, PhotoScan

## Tier 3 — Longtail / SEO / Wissenschaft (Monat 2+)

### Blog-Content auf andrestiebitz-site
- "Warum ich ImageRect gebaut habe" (persönliche Story, SEO für
  Karriere-Strategie Pfad A)
- "Homographie in 500 Zeilen Python" (technischer Deep-Dive,
  Programmierer-Publikum)
- "Fassadendokumentation für Architekten mit Open-Source-Tools"
  (Praxis-Tutorial mit St.-Georg-Daten)

### YouTube
- Eigener Kanal oder als Gast auf bestehenden (Jeff Geerling-Style
  dokumentieren — passt zum Backlog-Item "Jeff Geerling studieren")
- 3-5 Minuten Demo mit Echt-Daten
- 15-Minuten-Tutorial für Archäologen/Architekten

### Akademische Sichtbarkeit (wenn Zeit)
- **Zenodo** — DOI für jedes Release (zitierbar)
- **Journal of Open Source Software (JOSS)** — Peer-Review-Paper
  für Open-Source-Software, 2-4 Seiten, sehr niedrige Einstiegshürde.
  Passt perfekt für ImageRect.
- **arXiv** — falls technischer Beitrag (z.B. neuer
  Homographie-Solver-Vergleich)

### Listicle / Fachmedien
- **Open Source GIS Blog** (osgeo.org News) — Einreichung
- **Linux Magazin / iX** — News-Tipp bei stabilem Release
- **c't** — Projekt-Pitch (deutsch, hat auch mal Open-Source-Tools)
- **FOSSGIS-Konferenz** — Vortragseinreichung (jährlich März,
  Einreichungsfrist meist November)

### Product Hunt
- Einmaliger Launch-Tag, Mittwoch ist üblich
- Braucht vorbereitetes Netzwerk (Upvotes in ersten 4h entscheiden)
- Zweitrangig — die Zielgruppe (Archäologen/Vermessung) ist nicht
  PH-typisch. Nur wenn Launch-Momentum da ist.

## Nicht machen (bewusst)

- **Product-Hunt ohne vorbereitetes Netzwerk** — verbrennt die Chance
- **Spam-Cross-Posts** auf 15 Subreddits gleichzeitig
- **LinkedIn-Massen-Invites** — Andre hat Karriere-Strategie-Ziele,
  aber Projekt-Promo und Self-Branding sollten nicht gemischt werden
- **Twitter/X** — Publikum ist weggezogen, Mastodon hat die
  Tech/Open-Source-Leute
- **Dev.to / HackerNoon** — wenn Blog-Post, dann auf andrestiebitz-site
  (Hoheit über eigene Plattform)

## Reihenfolge (konkret)

```
v0.2.1 released + Installer funktioniert + 4 Screenshots + 1 GIF
  ↓
README.md aufhübschen mit Hero-GIF
  ↓
Show HN + r/Photogrammetry + Mastodon-Thread — innerhalb 48h, dann
Traffic-Spitze beobachten
  ↓
Woche 2: r/Archaeology + r/Architecture + FOSSGIS-ML
  ↓
Woche 3: AlternativeTo + awesome-* PRs + PyPI
  ↓
Woche 4+: Blog-Post, YouTube-Demo, Landesdenkmalämter anschreiben
  ↓
Monat 2: JOSS-Paper schreiben, Zenodo-DOI, FOSSGIS-Vortrag einreichen
```

## Metriken (damit man weiß ob's wirkt)

- GitHub Stars (simpel, Grundsignal)
- GitHub Issues mit "real user" statt "developer" — erste bezahlte
  oder externe Bug-Reports
- Download-Zählung Release-Binaries
- Referrer-Logs auf andrestiebitz-site
- "Hast du ImageRect schon gesehen" — unsolicited Erwähnungen
  (Google Alert auf "imagerect")
