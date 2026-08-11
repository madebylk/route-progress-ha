# Route Progress for Home Assistant

[![Validate Home Assistant integration](https://github.com/madebylk/route-progress-ha/actions/workflows/validate-hacs.yaml/badge.svg)](https://github.com/madebylk/route-progress-ha/actions/workflows/validate-hacs.yaml)
[![Open your Home Assistant instance and add this repository to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=madebylk&repository=route-progress-ha&category=integration)

Eine HACS-kompatible Home-Assistant-Custom-Integration für den selbst gehosteten
Route-Progress-Dienst. Sie erstellt
auf Knopfdruck einen Freigabelink, übermittelt den Routenfortschritt und beendet
die Freigabe bei einem Zielwechsel.

## Installation

1. Dieses Repository in HACS als benutzerdefiniertes Repository vom Typ
   **Integration** hinzufügen oder den Button oben verwenden.
2. **Route Progress** in HACS installieren.
3. Home Assistant neu starten.
4. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach
   **Route Progress** suchen.

Für eine manuelle Installation den Ordner `custom_components/route_progress`
nach `/config/custom_components/route_progress` kopieren und Home Assistant neu
starten.

## Einrichtung

Im Anlege- und Bearbeiten-Dialog werden Home-Assistant-Entities direkt über
Entity-Selektoren ausgewählt.

Pflichtfelder:

- Zielname
- Zielposition mit den Attributen `latitude` und `longitude`
- Fahrzeugposition mit den Attributen `latitude` und `longitude`

Optionale Felder:

- Fahrtrichtung
- Geschwindigkeit
- ETA als Zeitstempel oder Minuten
- Reststrecke
- Verkehrsverzögerung
- geplante Lademinuten
- Ladestatus
- erwarteter Akku bei Ankunft

Zusätzlich werden die öffentliche Route-Progress-URL, der in
den Zugangsdaten konfigurierte Bearer-Token und ein
Aktualisierungsintervall zwischen 10 und 300 Sekunden benötigt.

Ist `/api/v1` zusätzlich durch Cloudflare Access geschützt, kann im Dialog
**Cloudflare Access verwenden** aktiviert werden. Die Integration fordert dann
die Client-ID und das Client-Secret eines Cloudflare Access Service-Tokens an
und sendet sie bei allen API-Aufrufen als `CF-Access-Client-Id` und
`CF-Access-Client-Secret`. Ohne aktivierten Schalter bleiben beide Angaben
optional und es werden keine Cloudflare-Access-Header gesendet.

## Verhalten

Sobald ein gültiges Ziel und eine Fahrzeugposition vorliegen, kann die Fahrt mit
dem Button `button.route_progress_start_share` manuell gestartet werden. Die
Integration speichert die zurückgelieferte Share-URL und sendet danach
fortlaufend Updates. Ändert sich der Zielname oder die Zielposition, wird die
laufende Freigabe beendet. Ohne Betätigung des Buttons wird keine Freigabe
erstellt.

Die Integration stellt folgende Entities bereit:

- `sensor.route_progress_share_url`
- `binary_sensor.route_progress_active_share`
- `button.route_progress_start_share`
- `button.route_progress_finish_share`

Fahrt-ID, Zielkennung und Share-URL werden im Home-Assistant-Speicher persistiert.
Das API-Token bleibt ausschließlich im Config Entry.

## Releases

Pull Requests und Pushes werden mit HACS und Hassfest validiert. Ein Release wird
über **Actions → Publish HACS release → Run workflow** erstellt. Die dort
eingegebene Version muss der `version` in
`custom_components/route_progress/manifest.json` entsprechen.

## Backend

API, Docker-Setup und Server-Dokumentation befinden sich in
der internen Server-Dokumentation.
