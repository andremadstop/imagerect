# ImageRect: Technisches Referenzhandbuch & Anwender-Tutorial

**Version:** 0.2.0 (Sanierter Stand)
**Status:** Kanonisch
**Autor:** Gemini CLI (Revisionseinheit)

---

## 1. Kernkonzept: Das "Metric First"-Prinzip
ImageRect ist kein gewöhnliches Bildbearbeitungsprogramm. Es ist ein photogrammetrisches Präzisionswerkzeug zur **metrischen Entzerrung** von Digitalfotos auf Basis von 2D-CAD-Daten (DXF) oder 3D-Referenzen (E57, OBJ).

**Die goldene Regel:** Eine Entzerrung ist nur so gut wie ihre Kontrollpunkte. Wer schlampt, erzeugt Datenmüll.

---

## 2. Die Workspaces (Arbeitsbereiche)

Die Applikation ist in spezialisierte Workspaces unterteilt, um die kognitive Last zu trennen (Separation of Concerns).

### A. Project Hub (Die Schaltzentrale)
*   **Funktion:** Verwaltung von Projekten und schneller Zugriff auf letzte Dateien.
*   **UX-Features:**
    *   **Live-Summary:** Zeigt sofort an, wie viele Bilder geladen sind und ob das Projekt "dirty" (ungespeichert) ist.
    *   **Quick-Actions:** Direkter Sprung in die spezialisierten Ansichten.

### B. Rectify Workspace (Das Herzstück)
*   **Funktion:** Paarung von Bildkoordinaten mit Referenzkoordinaten.
*   **Funktionen:**
    *   **Control Point Pairing:** Setzen von Punkten im Foto (links) und in der CAD-Referenz (rechts).
    *   **Residual-Analyse:** Echtzeit-Berechnung des RMS-Fehlers. Punkte mit hohem Fehler werden farblich markiert (Gelb > 1px, Rot > 5px).
    *   **Lens Correction:** Anwendung von Linsenprofilen zur Eliminierung von Verzeichnung (K1, K2 Parameter). Ohne Korrektur ist keine metrische Präzision möglich.
*   **UX-Features:**
    *   **Cross-Cursor Sync:** Das Bewegen über einen Punkt in der Tabelle hebt ihn in beiden Viewern hervor.
    *   **Modifier-Clicks:** `Strg+Klick` zum schnellen Setzen von Punkten.

### C. 3D Workspace (Projektionsebene)
*   **Funktion:** Definition einer 2D-Arbeits-Ebene in einem 3D-Modell.
*   **Funktionen:**
    *   **3-Punkt-Ebene:** Definition der Projektionsfläche durch Auswahl von drei Punkten im Raum.
    *   **RANSAC-Fitting:** Automatisches Finden der besten Ebene in einer Punktwolke.
*   **UX-Features:**
    *   **Interactive 3D-Rotation:** Vollständige Navigation in Punktwolken (E57) und Meshes (OBJ).

### D. Review & Export (Die Endkontrolle)
*   **Funktion:** Visuelle Prüfung der Überlagerung und finaler Dateiexport.
*   **Funktionen:**
    *   **Layer-Opacity:** Stufenlose Transparenz zwischen entzerrtem Foto und DXF-Overlay.
    *   **Metric Tiling:** Unterstützung für Gigapixel-Exporte durch gekacheltes Rendering.
    *   **Mosaic-Mode:** Zusammenfügen mehrerer Bilder zu einem Gesamtplan.

---

## 3. Schritt-für-Schritt Tutorial

### Schritt 1: Projekt-Setup
1.  Starten Sie die App über das Desktop-Symbol.
2.  Wählen Sie im Hub **"New 2D Project"**.
3.  Laden Sie Ihr Quellbild (`Bild -> Bild laden`).
4.  Laden Sie Ihre Referenz (z.B. ein DXF des Aufmaßes).

### Schritt 2: Die Paarung (Alignment)
1.  Suchen Sie markante Stellen im Bild (Ecken, Kanten).
2.  Klicken Sie im linken Viewer auf den Punkt. Ein neuer Kontrollpunkt (z.B. P01) wird erstellt.
3.  Suchen Sie denselben Punkt in der DXF-Referenz (rechts) und klicken Sie darauf.
4.  Wiederholen Sie dies für **mindestens 4 Punkte**. (Mathematisches Minimum für die Homographie).
    *   *Profi-Tipp:* Verteilen Sie die Punkte über das gesamte Bild, nicht nur in einer Ecke.

### Schritt 3: Präzisions-Check
1.  Prüfen Sie den **RMS-Fehler** in der Statusleiste oder Tabelle.
2.  Sollte der Fehler > 2.0 Einheiten sein, prüfen Sie die Punkte oder wenden Sie eine **Linsenkorrektur** an (`Bild -> Objektiv-Korrektur`).

### Schritt 4: Export
1.  Wechseln Sie in den **Review Workspace**.
2.  Stellen Sie die gewünschte Zielauflösung (DPI) und die Pixelgröße (mm/Pixel) ein.
3.  Klicken Sie auf **Export**.
4.  Wählen Sie das Format:
    *   **TIFF:** Für GIS/CAD-Integration (inkl. GeoTIFF-kompatiblen Metadaten).
    *   **PNG/JPEG:** Für Dokumentationszwecke.

---

## 4. Technische Spezifikationen (Die Regeln)

*   **Metadaten-Sidecar:** Zu jedem Export wird eine `.json`-Datei generiert. Diese enthält die vollständige Transformationsmatrix und die Kamera-Pose.
*   **BigTIFF:** Bei Dateien > 4GB schaltet das System automatisch auf 64-Bit-Offsets um.
*   **Coordinate Systems:** Unterstützt EPSG-basierte Transformationen (benötigt `pyproj`), um GPS-Daten aus Drohnenbildern direkt auf CAD-Koordinaten zu mappen.

---

## 5. Auditor-Anmerkung zur Bedienung
Die Benutzeroberfläche folgt dem **"Dienst nach Vorschrift"-Prinzip**:
*   Aktionen, die nicht möglich sind (z.B. Export ohne Punkte), sind **ausgegraut**.
*   Fehler werden im **Diagnose-Paket** (`Hilfe -> Diagnose-Paket erstellen`) gesammelt.
