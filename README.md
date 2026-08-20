# Route Progress for Home Assistant

[![Latest release](https://img.shields.io/github/v/release/madebylk/route-progress-ha)](https://github.com/madebylk/route-progress-ha/releases/latest)
[![Validate Home Assistant integration](https://github.com/madebylk/route-progress-ha/actions/workflows/validate-hacs.yaml/badge.svg)](https://github.com/madebylk/route-progress-ha/actions/workflows/validate-hacs.yaml)
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=madebylk&repository=route-progress-ha&category=integration)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Route Progress ist eine benutzerdefinierte Home-Assistant-Integration, die den
Fortschritt einer laufenden Route über einen zeitlich begrenzten Link teilbar
macht. Die Daten stammen ausschließlich aus den in Home Assistant ausgewählten
Entities.

Dieses Repository enthält nur die quelloffene Home-Assistant-Integration. Der
zugehörige Route-Progress-Dienst ist nicht Bestandteil dieses Repositorys und
wird hier nicht als installierbare Server-Software angeboten. Für die Nutzung
werden eine Dienst-URL und bereitgestellte Zugangsdaten benötigt.

## Funktionen

- Freigabelink direkt über eine Home-Assistant-Button-Entity starten
- Position, Ziel, ETA, Reststrecke und weitere optionale Routendaten übermitteln
- Zielwechsel erkennen und bewusst übernehmen
- Freigabe manuell beenden
- Verbindungs- und Freigabestatus als Home-Assistant-Entities anzeigen
- Laufende Fahrt nach einem Home-Assistant-Neustart fortsetzen
- Deutsche und englische Oberfläche

## Voraussetzungen

- Home Assistant mit HACS oder die Möglichkeit zur manuellen Installation
- URL eines erreichbaren Route-Progress-Dienstes
- ein für die Home-Assistant-Instanz bereitgestellter Zugriffstoken
- Cloudflare-Access-Client-ID und -Client-Secret
- passende Home-Assistant-Entities für Ziel und Fahrzeugposition

Die Route-Progress-API unter `/api/v1` ist durch Cloudflare Access geschützt.
Die Integration übermittelt die bereitgestellten Access-Daten bei den
API-Aufrufen in den dafür vorgesehenen Headern.

## Installation mit HACS

1. Den Button **Open in HACS** oben verwenden oder dieses Repository in HACS als
   benutzerdefiniertes Repository vom Typ **Integration** hinzufügen.
2. **Route Progress** in HACS installieren.
3. Home Assistant neu starten.
4. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach
   **Route Progress** suchen.

## Manuelle Installation

Den Ordner `custom_components/route_progress` nach
`/config/custom_components/route_progress` kopieren und Home Assistant neu
starten. Updates müssen bei dieser Installationsart ebenfalls manuell
eingespielt werden.

## Einrichtung

Im Einrichtungsdialog werden zuerst die Dienst-URL, der Zugriffstoken und das
Aktualisierungsintervall zwischen 10 und 300 Sekunden eingetragen. Aktiviere
**Cloudflare Access verwenden** und ergänze die bereitgestellte Client-ID und
das Client-Secret.

Anschließend werden die Datenquellen direkt über Home-Assistant-Entity-Selektoren
ausgewählt.

Erforderlich sind:

- Zielname
- Zielposition mit den Attributen `latitude` und `longitude`
- Fahrzeugposition mit den Attributen `latitude` und `longitude`

Optional können konfiguriert werden:

- Fahrtrichtung
- Geschwindigkeit
- ETA als Zeitstempel oder Minutenwert
- Reststrecke
- Verkehrsverzögerung
- geplante Lademinuten
- Ladestatus
- erwarteter Akku bei Ankunft

## Verwendung

`button.route_progress_start_share` erzeugt einen Freigabelink. Sobald die
konfigurierte Fahrzeugpositions-Entity aktualisiert wird, sendet die Integration
nach einer kurzen Sammelphase einen vollständigen Snapshot der ausgewählten
Routendaten. Das konfigurierte Intervall sendet denselben vollständigen Zustand
zusätzlich als Heartbeat.

Ein stabiles Ziel wird vom Dienst bestätigt. Bei einem späteren Zielwechsel
wird die öffentliche Route eingefroren, bis das ursprüngliche Ziel zurückkehrt
oder das neue Ziel mit `button.route_progress_accept_destination` übernommen
wird. Mit `button.route_progress_finish_share` lässt sich die Freigabe jederzeit
beenden.

Den Zustand der konfigurierten Navigations-Entities übermittelt die Integration
neutral als `present`, `absent` oder `unknown`, ohne daraus eine
anbieterspezifische Fahrerabsicht abzuleiten. Zielname und Zielposition werden
dabei als gemeinsamer Snapshot stabilisiert: Kehrt nach einer
`absent`-/`unknown`-Lücke eindeutig derselbe Zielname zurück, darf dessen letzte
vollständige Position wiederverwendet werden. Ein anderer Zielname benötigt
immer eine neue, zeitlich passende Zielposition. Ein explizites `absent` bleibt
in jedem Fall `absent`. Nur der Dienst entscheidet anhand dieser neutralen
Beobachtungen über Fahrerabsicht, Zielbestätigung und Fahrtlebenszyklus.

Fehlt die Navigation außerhalb des Zielbereichs, friert der Dienst die
öffentliche Position zunächst im Status `navigation_uncertain` ein. Kehrt das
ursprüngliche Ziel zurück, wird die Fahrt automatisch fortgesetzt. Numerische
Null-Sentinels für ETA, Reststrecke und erwarteten Akku werden während eines
unvollständigen Navigations-Snapshots nicht übertragen; legitime Nullwerte wie
Verkehrsverzögerung, Ladezeit und Ladestatus bleiben erhalten.

Die Integration stellt folgende Entities bereit:

| Entity | Zweck |
| --- | --- |
| `sensor.route_progress_share_url` | Aktueller oder zuletzt erstellter Freigabelink |
| `sensor.route_progress_share_status` | Lebenszyklusstatus der Freigabe |
| `binary_sensor.route_progress_active_share` | Zeigt eine aktive Freigabe an |
| `binary_sensor.route_progress_cloud_connection` | Diagnose der Dienstverbindung |
| `button.route_progress_start_share` | Startet eine neue Freigabe |
| `button.route_progress_accept_destination` | Übernimmt ein geändertes Ziel |
| `button.route_progress_finish_share` | Beendet die aktuelle Freigabe |

## Datenschutz und Sicherheit

- Ohne Betätigung des Start-Buttons wird keine Freigabe erstellt.
- Übermittelt werden nur Werte aus den ausdrücklich konfigurierten Entities.
- Zugriffstoken und Cloudflare-Access-Daten werden im Home-Assistant-Config-Entry
  gespeichert und nicht als Entity-Attribute ausgegeben.
- Fahrt-ID, Status und Freigabelink werden lokal in Home Assistant gespeichert,
  damit eine laufende Freigabe einen Neustart übersteht.
- Debug-Logs können Zustands-, Routen- und API-Daten enthalten und sollten nur
  gezielt und vorübergehend aktiviert werden. Freigabelinks und bekannte
  Zugangsdatenfelder werden vor der Ausgabe redigiert.

Sicherheitsprobleme bitte nicht in einem öffentlichen Issue melden. Hinweise
dazu stehen in [SECURITY.md](SECURITY.md).

## Fehlerdiagnose

Für eine gezielte Analyse kann Debug-Logging aktiviert werden:

```yaml
logger:
  logs:
    custom_components.route_progress: debug
```

Vor dem Teilen von Logs müssen Tokens, Freigabelinks, Entity-Namen und andere
persönliche Daten entfernt werden.

## Support und Beiträge

Fehlerberichte und Funktionsvorschläge können über die
[GitHub Issues](https://github.com/madebylk/route-progress-ha/issues) eingereicht
werden. Bitte vorher prüfen, ob bereits ein passendes Issue existiert.

Hinweise für Pull Requests stehen in [CONTRIBUTING.md](CONTRIBUTING.md).

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
