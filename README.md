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

Der Button `button.route_progress_start_share` erzeugt sofort einen teilbaren
Link. Ein Ziel oder eine Fahrzeugposition werden dafür noch nicht benötigt. Das
Backend übernimmt das erste mindestens 60 Sekunden stabile Navigationsziel und
erkennt Zielabweichungen. Innerhalb von 300 Metern bestätigt es die Ankunft nach
zwei Minuten mit exakt `0 km/h`. Fehlt der Geschwindigkeitswert, greift nach zehn
Minuten im Zielbereich ein Positions-Fallback.

Bei einem abweichenden Navigationsziel friert der Server die öffentlich sichtbare
Route ein. Kehrt das ursprüngliche Ziel zurück, wird die Fahrt automatisch
fortgesetzt. Eine bewusst im Fahrzeug gelöschte Route führt im Zustand
`en_route` ebenfalls zu diesem eingefrorenen Zustand; erst die bereits erkannte
Ankunfts-Nachlaufphase behält ihre Parkplatzsuchlogik. Eine vorübergehend
`unknown` oder `unavailable` gewordene Quell-Entity wird davon unterschieden.
Mit `button.route_progress_accept_destination` kann ein neues Ziel bewusst
übernommen werden. Bereits gefahrener Track, ursprünglicher Startpunkt und
bisherige Statistiken bleiben dabei erhalten; nur die verbleibende Route wird
neu berechnet. Nach erkannter Ankunft sendet die Integration noch
zehn Minuten Fahrtdaten, damit die Darstellung bis zur Parkposition aufholt.
Weiterfahrt oder Verlassen des Zielbereichs widerruft diese vorläufige Ankunft.
Danach beziehungsweise nach manuellem Beenden werden keine weiteren Fahrtdaten
gesendet; der Link bleibt bis zu seinem Ablauf erreichbar.

Die Integration trifft keine eigenen Entscheidungen über den Fahrtverlauf. Sie
übermittelt Home-Assistant-Snapshots und stellt den vom Backend gelieferten
Lebenszyklusstatus dar. Beim Start wird ein bereits vorhandenes Navigationsziel
sofort übermittelt. Bei jeder Aktualisierung der Fahrzeugpositions-Entity wird
eine Sekunde auf zusammengehörige Werte gewartet und anschließend ein
vollständiger Snapshot aller konfigurierten Routendaten gesendet. Änderungen
beliebiger anderer Entities lösen keinen separaten, möglicherweise
inkonsistenten Zwischen-Snapshot aus. Das konfigurierte Intervall übermittelt
den vollständigen aktuellen Zustand zusätzlich als Heartbeat für serverseitige
Bestätigungen und Timer.

Der Messzeitpunkt der Fahrzeugposition ändert sich nur zusammen mit Latitude
oder Longitude. Wiederholt die konfigurierte Entity-Quelle dieselben Koordinaten mit einem neuen
`last_updated`, bleibt der ursprüngliche GPS-Zeitpunkt erhalten. Ein fehlender
Heading-Wert bleibt dabei explizit unbekannt; die Karte richtet den Marker dann
an der Route aus und verwendet keinen aus Positionswanderungen geschätzten
Ersatzwert.
Während einer laufenden Ankunftsbestätigung sendet die Integration davon
getrennte Beobachtungen an das Backend. Diese ändern keine öffentlich sichtbaren
Fahrtdaten. Ohne Betätigung des Start-Buttons wird keine Freigabe erstellt.

Die Integration stellt folgende Entities bereit:

- `sensor.route_progress_share_url`
- `sensor.route_progress_share_status`
- `binary_sensor.route_progress_active_share`
- `binary_sensor.route_progress_cloud_connection` (Diagnose)
- `button.route_progress_start_share`
- `button.route_progress_accept_destination`
- `button.route_progress_finish_share`

Fahrt-ID, Serverstatus und Share-URL werden im Home-Assistant-Speicher
persistiert. Das API-Token bleibt ausschließlich im Config Entry.

## Releases

Pull Requests und Pushes werden mit HACS und Hassfest validiert. Ein Release wird
über **Actions → Publish HACS release → Run workflow** erstellt. Die dort
eingegebene Version muss der `version` in
`custom_components/route_progress/manifest.json` entsprechen.

## Backend

API, Docker-Setup und Server-Dokumentation befinden sich in
der internen Server-Dokumentation.

# Development logging

To trace entity snapshots, synchronization decisions, API payloads, and server responses, enable Home Assistant debug logging:

```yaml
logger:
  logs:
    custom_components.route_progress: debug
```
