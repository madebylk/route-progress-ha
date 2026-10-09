# Route Progress for Home Assistant

[![Latest release](https://img.shields.io/github/v/release/madebylk/route-progress-ha)](https://github.com/madebylk/route-progress-ha/releases/latest)
[![Validate Home Assistant integration](https://github.com/madebylk/route-progress-ha/actions/workflows/validate-hacs.yaml/badge.svg)](https://github.com/madebylk/route-progress-ha/actions/workflows/validate-hacs.yaml)
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=madebylk&repository=route-progress-ha&category=integration)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Route Progress turns Home Assistant journey data into a polished live page that you can share with friends and family. Recipients need no account and no app: one temporary, read-only link shows where the journey stands and what to expect next.

> [!IMPORTANT]
> **This integration requires a separate, non-public Route Progress server component.** This repository contains only the Home Assistant integration; the server source code is not publicly available and the server is not included in the HACS or manual installation. You need access to an existing server, its service URL, and credentials from its operator before you can use the integration. Installing this integration alone does not provide a working Route Progress service.

## How the components fit together

- **Home Assistant integration (this repository):** reads your selected entities, sends journey data to the server, and provides share controls and the resulting link in Home Assistant.
- **Route Progress server (non-public, required):** processes journey data, manages shares and their expiry, and serves the live pages shown in the screenshots below.
- **Shared page:** friends and family open the temporary link in their browser, without a Home Assistant account or app.

The screenshots show the server-hosted pages that become available when the integration is connected to that server.

![Route Progress live journey with the complete road route, driven track, current vehicle position, destination, ETA, and remaining distance](docs/images/showcase-live-route-desktop.png)

The map makes progress immediately understandable: the driven section is grey, the remaining road route is blue, and the live vehicle marker sits between the start and destination. ETA, remaining time, distance, traffic delay, and charging time stay visible above the map.

## From one button to a live share

1. Press **Start share** in Home Assistant.
2. Route Progress immediately creates a unique, unguessable link that is valid for 24 hours.
3. Copy the link from Home Assistant and send it to friends, family, or anyone waiting for you.
4. The public page updates as the vehicle moves. It is read-only and never exposes Home Assistant access.
5. Press **Finish share** when needed. The completed page remains readable until its normal 24-hour expiry.

The share exists immediately, even before navigation and the first vehicle position arrive:

![A newly created Route Progress share waiting for the journey to begin](docs/images/route-progress-share-created.png)

As soon as trip data arrives, the same link becomes the live map shown above. No new link needs to be sent.

## Built for every screen

The responsive layout keeps the complete journey useful on a phone: status, progress, ETA, distance, map, markers, legend, and map controls remain available without installing an app.

<p align="center">
  <img src="docs/images/showcase-live-route-mobile.png" width="420" alt="Responsive mobile Route Progress page with live map, road route, progress, ETA, and distance">
</p>

## More than a moving dot

Route Progress translates the incoming Home Assistant entities into clear journey states. Viewers can tell whether the vehicle is moving normally, delayed by traffic, stopped to charge, waiting to depart, or already at the destination.

| Traffic-aware progress | Charging stops |
| --- | --- |
| The status changes to **In traffic**, the delay is called out, and the driven and remaining route stay visible. | The page changes to **Charging stop** and shows the planned charging time alongside the live journey. |
| ![Route Progress showing a traffic delay on a real road route](docs/images/showcase-traffic-delay.png) | ![Route Progress showing a charging stop and planned charging time](docs/images/showcase-charging-stop.png) |

## A useful record until the link expires

When the destination is reached, Route Progress presents the completed route, arrival time, total journey duration, and travelled distance. The frozen result remains available through the same link until its 24-hour expiry.

![Completed Route Progress journey showing arrival details and the full driven road route](docs/images/showcase-trip-arrived.png)

All screenshots above were captured from real, locally running Route Progress demo journeys using calculated road routes. They are not interface mock-ups.

## Features
- Create a share link through a Home Assistant button entity or a freely placed dashboard card
- Choose destinations from entities, Geoapify search, Google Maps links or HA zones
- Send position, destination, ETA, remaining distance, and optional route data
- Detect destination changes and accept them deliberately
- Finish a share manually at any time
- Expose connection and share status as Home Assistant entities
- Resume an active trip after a Home Assistant restart
- German and English user interface
- Configurable update interval from 10 to 300 seconds

## Requirements

- Access to the **separate, non-public Route Progress server component**; this repository cannot be used to install or self-host that server
- Home Assistant with HACS, or support for manual custom-integration installation
- URL of a reachable Route Progress service
- API token issued for this Home Assistant instance
- Cloudflare Access client ID and client secret when required
- A position entity with latitude/longitude (vehicle or smartphone)
- Either destination entities, or manual destination selection; a Geoapify API key enables address search in manual mode

## Installation with HACS

Before installing, make sure you already have server access and credentials from the service operator. HACS installs only the Home Assistant integration.

1. Use the **Open in HACS** badge above, or add https://github.com/madebylk/route-progress-ha to HACS as a custom repository of type **Integration**.
2. Install **Route Progress** in HACS.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and search for **Route Progress**.

## Manual installation

With server access and credentials already available, copy custom_components/route_progress to /config/custom_components/route_progress and restart Home Assistant. This installs only the integration. Updates must also be installed manually when using this method.

## Setup

Enter the service URL and API token supplied by your Route Progress server operator, and an update interval between 10 and 300 seconds. Enable **Use Cloudflare Access** and enter the supplied client ID and client secret when required. These credentials must come from the existing server; installing the integration does not create them.

Choose a **Destination source** in the first setup step (also available under **Reconfigure**):

| Source | Second setup step | Use case |
| --- | --- | --- |
| Automatically from entities | Destination name and destination coordinates entities | Vehicles/integrations that expose their navigation target |
| Manual: search, Maps link or HA zone | Optional Geoapify API key | Any vehicle, including journeys tracked by a smartphone |

Both modes require a position entity with `latitude` and `longitude` attributes. Existing installations keep entity mode automatically. Finish an active share before switching modes. Switching to entity mode removes the stored Geoapify key from the integration configuration.

The Geoapify field appears **only in manual mode**. Leave it empty if you only use HA zones or supported Maps links with explicit destination coordinates. Text searches and links containing only an address need a key.

Optional entities:

- Heading
- Speed
- ETA as a timestamp or number of minutes
- Remaining distance
- Traffic delay
- Planned charging time
- Charging status
- Estimated battery level at arrival

## Best practices: manual destination selection

### 1. Configure the source once

Select **Manual: search, Maps link or HA zone**, choose a smartphone or vehicle GPS entity, and enter your own [Geoapify API key](https://myprojects.geoapify.com/) in the second step if you want address search. Home Assistant calls Geoapify directly. Neither the key nor your search queries are sent to the Route Progress server. The key is stored with the integration credentials, not in the card YAML or entity attributes. Treat Home Assistant backups as sensitive.

Geoapify has a free tier; consult its [current pricing](https://www.geoapify.com/pricing/) rather than assuming a permanent quota. One destination search can issue several autocomplete requests. Requests are delayed while you type and limited across users. Quota/authentication failures appear in the card without revealing credentials.

### Geoapify validation and connection diagnostics

When you save manual-mode setup or reconfiguration with a Geoapify key, the integration validates access to the autocomplete API using one fixed public-place query. Invalid credentials, quota limits and network failures appear on the key field; failed validation does not overwrite the existing configuration. Leaving the key empty skips validation and keeps zones and supported coordinate links usable.

A **Geoapify connection** diagnostic binary sensor appears on the integration's device page when manual mode and an API key are configured. It is independent of **Cloud connection**: a search-provider outage does not prevent sharing a saved target or selecting a HA zone. Its `last_checked`, `last_successful_connection` and safe `last_error` attributes explain the most recent observation. It represents the **last known result**, not a continuously monitored connection.

To conserve requests, successful checks are shared between setup and runtime for 15 minutes, failed checks for one minute. A known invalid key or exhausted quota also pauses further Geoapify search requests for that minute. A fresh HA process performs at most one initial check for the configured key; a recent setup check avoids another request on reload. Normal Geoapify searches refresh the diagnostic status themselves. There is **no periodic Geoapify health polling**, and refreshing the dashboard, reading the diagnostic sensor, choosing a zone or resolving a coordinate-only link does not issue a Geoapify request. Clearing/changing the key never reuses another key's status. Existing installations without a key and entity mode make no checks.

### 2. Add the dashboard card

The card is **bundled with the Route Progress integration**, starting with v0.14.0. HACS installs and updates both together. Do not add a second HACS dashboard repository, copy JavaScript into `/config/www`, or manually register a dashboard resource: the integration loads the card automatically.

**Prerequisites:** finish setting up the integration, select **Manual: search, Maps link or HA zone**, and configure a position entity. Existing installations remain in entity mode after an update; switch modes under **Settings → Devices & services → Route Progress → Reconfigure** before using this card. Finish an active share before changing the source. The card is for choosing manual destinations; entity mode continues to use the existing integration entities and buttons.

#### Add through the dashboard editor

1. After installing or updating the integration in HACS, restart Home Assistant to load the Python integration changes.
2. Reload the browser or Companion App frontend to load the bundled card.
3. Open the dashboard and view where the card should appear, then enter **Edit dashboard**.
4. Choose **Add card**, search for **Route Progress**, and select it.
5. Optionally change its title in the visual editor, then save the card and dashboard.

You can place the card in different dashboard views or include it in a stack. No entity IDs or API keys belong in the card configuration. Creating a card requires permission to edit the dashboard.

#### YAML configuration

Use this in the manual card editor, or under a view's `cards` list in a YAML dashboard:

```yaml
type: custom:route-progress-card
title: My journey
```

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `type` | Yes | — | Must be `custom:route-progress-card`. |
| `title` | No | `Route Progress` | Heading displayed at the top of the card. |

These are the card's configuration options. The integration owns the server connection, Geoapify key, position source and update interval. The card follows the Home Assistant language, with German and English supported.

#### Controls and shared state

| Control | What it does |
| --- | --- |
| Search field / Search | Find a place or address, or resolve a supported Google Maps link. |
| HA zones | Preview the selected zone as a destination. |
| Use destination | Save the previewed target; does not start a public share. |
| Share trip | Create a share using the saved destination; enabled when a destination is selected, the server is available and no share is active. |
| Change trip destination | Explicitly adopt the previewed target during an active share. |
| Accept new destination | Retry destination confirmation if the server still reports a pending target change. |
| Finish trip | Stop updates to the current share. |
| Copy link / Share link | Copy the link or open the device's share dialog where supported. |

Multiple cards control the **same single integration and shared trip**, not separate journeys. Normal Home Assistant entity permissions apply: users need control of the integration's start button and read access to its configured position entity. Zones are filtered by read access. Removing a card does not end a share or delete the integration; use **Finish trip** to stop sharing.

### 3. Choose and check the destination before starting

- **Search:** enter at least three characters of a place or address and select a result. Add a city or street when a place name is ambiguous. Results come from Geoapify; its OpenStreetMap-based data can differ from Google Maps listings.
- **Paste a Google Maps link:** use **Share → Copy link** on a single place in Google Maps. Supported `maps.app.goo.gl` and `goo.gl/maps` short links are expanded inside Home Assistant. Explicit destination coordinates are used directly; address-only links are searched with Geoapify. A Maps viewport is never treated as the target. Multi-stop/directions links without a single explicit destination, opaque place-ID-only links and unsupported formats are rejected with guidance to paste a place link or search the address.
- **HA zone:** select an existing zone to use its name and coordinates without a Geoapify request.

After selecting a result, the list collapses and the pending choice shows its name and full address. Check these details, optionally expand the native HA map preview or use **Open in maps**, then choose **Use destination → Share trip**. Selecting/searching alone never creates a public link. The optional HA map preview loads tiles through Home Assistant’s usual map provider; opening the external map sends the location to OpenStreetMap; Geoapify attribution remains visible with its results. Use **Copy link** or the device's **Share link** action to send the share yourself.

### Use standard HA entities instead of the custom card

Manual mode also creates the following entities on the integration's device. Add them to a normal **Entities** dashboard card using HA's entity picker; the actual entity IDs depend on your language and registry names. The custom Route Progress card is optional.

| Entity | Purpose |
| --- | --- |
| Text: Destination search / Maps link | Submit an address or Maps link. A submitted value performs one search, not one request per keystroke. Emptying it clears the search results. |
| Select: Use search result | Choose an explicitly numbered result with its address. Choosing an option saves that destination, and confirms a destination change during an active share. |
| Select: HA zone destination | Choose a zone by name and entity ID without Geoapify. The zone's coordinates are copied when selected. |
| Sensor: Selected destination | Saved destination name, with `latitude`, `longitude`, `address`, `source` and provider attribution attributes. Also usable in the standard HA Map card. |
| Buttons: Start share / Finish share | Start sharing the saved destination, or finish the current share. |

**Workflow:** submit the text value → choose a search result (or choose a HA zone directly) → check **Selected destination** → press **Start share**. No first result is chosen automatically, including coordinate links. Search results expire after ten minutes and are not restored after restart; repeat the search if expired. The confirmed target is restored. Search and zone selection work while the Route Progress server is offline; starting/sharing still requires that server.

The text entity accepts up to **255 characters**, matching HA's entity-state limit. Use a Google Maps short link or the custom card for longer links (up to 4096 characters). All cards and entities share one destination and journey. Entity searches/results are shared among users with access to those entities, so grant read/control permissions accordingly.

Automations can use the standard `text.set_value`, `select.select_option` and `button.press` actions with these entities. Choose a specific result from the select entity's `options` attribute; do not blindly select the first geocoding match. For predictable automations prefer the zone selector. No Geoapify key belongs in an automation or dashboard.


### 4. Keep the journey predictable

The chosen destination is saved in Home Assistant and survives restarts. A zone is copied when selected: later zone edits do not silently move an active journey's target. During a share, selecting another target and pressing **Change trip destination** explicitly accepts that change. If the server is unavailable, the chosen target stays saved; retry or use **Accept new destination** after reconnection if confirmation remains pending.

With server v0.14.0 or later, a manually selected target is explicitly confirmed when sharing starts, without the one-minute stabilization period used for automatic navigation entities. Older servers retain their previous confirmation flow; update the server and reload the integration to enable immediate confirmation. “Sharing active” means that the public share is running, not that vehicle movement has been detected. “Confirming navigation destination” means the older/automatic flow is still waiting for stable destination data and a fresh source observation. Missing vehicle navigation entities do not pause a manually selected target. Position timestamps still reflect real GPS observations; reducing the integration interval cannot make the phone report new GPS coordinates. Enable the appropriate background location permissions in the Companion App and monitor position freshness.

With an updated Route Progress server, absent ETA/distance values are filled from road-routing estimates and marked as estimates. The estimated time is scaled as the remaining route shortens and does not include live traffic or charging plans. Supplied vehicle metrics take precedence. If routing fails or the server is older, these values may remain unavailable. Leave destination-dependent vehicle metrics (ETA, remaining distance, traffic, charging plan, arrival battery) unconfigured when they refer to a different navigation target.

## Usage

button.route_progress_start_share creates the unique 24-hour share link immediately. When the configured vehicle-position entity changes, the integration sends a complete snapshot of the selected route data after a short collection period. The configured interval also sends the complete current state as a heartbeat.

The service confirms a stable destination. If the destination later changes, the public route is frozen until the original destination returns or the new destination is accepted with button.route_progress_accept_destination. Use button.route_progress_finish_share to stop a share manually.

The integration reports navigation state neutrally as present, absent, or unknown. The service alone decides driver intent, destination confirmation, and the journey lifecycle.

| Entity | Purpose |
| --- | --- |
| sensor.route_progress_share_url | Current or most recently created share link |
| sensor.route_progress_share_status | Server-side share lifecycle status |
| binary_sensor.route_progress_active_share | Whether a share is active |
| binary_sensor.route_progress_cloud_connection | Service connection diagnostics |
| binary_sensor.route_progress_geoapify_connection | Last known Geoapify connectivity; manual mode with a configured key only |
| button.route_progress_start_share | Create a new share |
| button.route_progress_accept_destination | Accept a changed destination |
| button.route_progress_finish_share | Finish the active share |

Trip ID, status, and share link are stored locally in Home Assistant so an active share survives a restart. Credentials are never exposed as entity attributes.

## Privacy and security

- No share is created until the start button is pressed.
- Only configured entity values and the explicitly selected destination are sent to the share server. Manual search text goes directly from Home Assistant to Geoapify; pasted Maps short links are resolved with Google.
- The public link is read-only and expires after 24 hours.
- API, Geoapify and Cloudflare Access credentials stay in the Home Assistant config entry.
- Debug logs can contain state, route, and API data and should be enabled only temporarily.
- Share links and known credential fields are redacted from integration logs.

Do not report security vulnerabilities in a public issue. See [SECURITY.md](SECURITY.md).

## Troubleshooting

### Dashboard card

| Symptom | Check |
| --- | --- |
| Route Progress is missing from the card picker, or `Custom element doesn't exist: route-progress-card` | Confirm integration v0.14.0 or newer is installed and the integration loaded successfully. Restart HA after the integration update, then reload the browser/Companion App. If needed, try a hard refresh. Do not add duplicate manual resources. |
| Manual destinations are disabled | Reconfigure the integration and select manual mode; updating an existing installation deliberately preserves entity mode. |
| No permission to control this trip | Check the user's access to the configured position entity and the Route Progress start button. Dashboard visibility alone does not grant these permissions. |
| Address search asks for an API key | Enter a Geoapify key in the integration's manual-mode setup step, not in the card YAML. Zones and coordinate-bearing Maps links can work without it. |
| API key rejected or quota reached | Check the Geoapify key/account and current quota, then retry. Avoid repeatedly submitting the same failing request. |
| Maps link cannot be resolved | Copy the link for a single place. For ambiguous directions, viewport-only or unsupported links, search for the address instead. |
| Share trip is disabled | Select and confirm a destination, check the server connection, and finish any active share first. |
| Map preview is empty | Check whether the browser can access OpenStreetMap. The displayed name and coordinates remain available for checking the target. |
| Share link button is missing | The browser does not expose native sharing; use Copy link. If clipboard access fails, the card selects the link for manual copying. |
| Another card shows the same journey | Expected: all cards connect to the same single integration. |

### Diagnostic logging

Enable debug logging temporarily:

~~~yaml
logger:
  logs:
    custom_components.route_progress: debug
~~~

Remove tokens, share links, entity names, and other personal information before sharing logs.

## Support and contributions

Use [GitHub Issues](https://github.com/madebylk/route-progress-ha/issues) for bug reports and feature requests. Check for an existing issue first.

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request guidelines.

## License

This project is available under the [MIT License](LICENSE).
