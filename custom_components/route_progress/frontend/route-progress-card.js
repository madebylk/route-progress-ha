/* Home Assistant hosts this dashboard card; credentials never enter its state. */
class RouteProgressCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.sequence = 0;
    this.busy = false;
    this.mutation = 0;
  }

  setConfig(config) {
    this.config = { ...config };
    if (this.initialized) this.el('card-title').textContent = this.config.title || 'Route Progress';
  }
  static getConfigElement() { return document.createElement('route-progress-card-editor'); }
  static getStubConfig() { return { type: 'custom:route-progress-card' }; }
  getCardSize() { return 5; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: 'auto' }; }

  set hass(value) {
    this._hass = value;
    if (!this.initialized) {
      this.initialized = true;
      this.lang = value.language?.startsWith('de') ? 'de' : 'en';
      this.build();
      this.refresh();
    }
  }

  connectedCallback() {
    if (!this.poll) this.poll = setInterval(() => this.refresh(), 10000);
    if (this.initialized) this.refresh();
  }

  disconnectedCallback() {
    clearInterval(this.poll);
    clearTimeout(this.timer);
    this.poll = null;
    this.sequence++;
  }

  t(de, en) { return this.lang === 'de' ? de : en; }
  el(id) { return this.shadowRoot.getElementById(id); }
  call(action, extra = {}) {
    return this._hass.callWS({ type: 'route_progress/destination', action, language: this.lang, ...extra });
  }

  build() {
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;color:var(--primary-text-color);font:400 14px/1.4 var(--ha-font-family-body,Roboto,sans-serif)}
        *{box-sizing:border-box}header{padding:16px 16px 0}header strong{font-size:20px;font-weight:500}main{padding:16px}
        h2{font-size:14px;font-weight:500;margin:16px 0 8px}p{margin:8px 0;color:var(--secondary-text-color)}h2,p,.result{overflow-wrap:anywhere}label{display:block;font-size:12px;color:var(--secondary-text-color);margin:0 0 6px}.search{display:flex;gap:8px}
        input{min-width:0;flex:1;width:100%;font:inherit;padding:10px 12px;border-radius:var(--ha-border-radius-md,8px);border:1px solid var(--divider-color);background:var(--card-background-color);color:inherit}
        button{font:inherit;font-weight:500;cursor:pointer;border:1px solid var(--divider-color);border-radius:var(--ha-border-radius-md,8px);padding:8px 12px;background:var(--card-background-color);color:var(--primary-color);min-height:40px}
        button:hover{background:var(--secondary-background-color)}button:focus-visible,input:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}button:disabled{opacity:.5;cursor:default}
        button[aria-pressed=true]{border-color:var(--primary-color);background:var(--secondary-background-color)}
        .primary{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:transparent}.primary:hover{filter:brightness(.95);background:var(--primary-color)}.row{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
        .result{display:block;text-align:left;width:100%;margin-top:4px;color:inherit;border:0;border-bottom:1px solid var(--divider-color);border-radius:0}.result small{display:block;color:var(--secondary-text-color);margin-top:2px;line-height:1.4;font-weight:400}
        section.card{padding:12px 0 0;margin-top:16px;border-top:1px solid var(--divider-color)}
        #preview{border-left:3px solid var(--primary-color);padding:0 0 0 12px;border-top:0}#preview h2{margin-top:4px}#preview-map{margin-top:8px;border-radius:8px;overflow:hidden}.muted{font-size:12px;color:var(--secondary-text-color)}
        a{color:var(--primary-color)}#message{white-space:pre-wrap}#message:empty{display:none}#message.error{color:var(--error-color,#b3261e)}[hidden]{display:none!important}
        #share-url{margin-top:4px}#share{margin-top:12px}#status{font-size:12px;margin:0 0 4px}.title{margin:0;font-size:16px;font-weight:500}#attribution{font-size:11px;margin-top:8px}#selected-address:empty{display:none}summary{cursor:pointer;color:var(--primary-color);padding:8px 0}#zones{margin-top:0}#selection-label{font-size:12px;color:var(--primary-color);margin:0}
        @media(max-width:320px){.search{flex-wrap:wrap}.search button{width:100%}}
      </style>
      <ha-card><header><strong id="card-title"></strong></header>
      <main>
        <label for="query">${this.t('Ort, Adresse oder Google-Maps-Link', 'Place, address or Google Maps link')}</label>
        <form id="search-form" class="search"><input id="query" type="text" maxlength="4096" autocomplete="off" placeholder="${this.t('Zum Beispiel: Hamburg Hauptbahnhof','For example: Hamburg Central Station')}"><button id="search" type="submit">${this.t('Suchen','Search')}</button></form>
        <p id="key-hint" class="muted" hidden>${this.t('Für die Adresssuche bitte einen Geoapify-Schlüssel in der Integration hinterlegen. HA-Zonen und Maps-Links mit Zielkoordinaten funktionieren ohne Schlüssel.', 'Configure a Geoapify key in the integration for address search. HA zones and Maps links containing destination coordinates work without a key.')}</p>
        <p id="message" role="status" aria-live="polite"></p>
        <div id="results" aria-label="${this.t('Suchergebnisse','Search results')}"></div>
        <div id="attribution" hidden>Powered by <a href="https://www.geoapify.com/" target="_blank" rel="noopener noreferrer">Geoapify</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a></div>
        <section><h2>${this.t('HA-Zonen','HA zones')}</h2><div id="zones" class="row"></div></section>
        <section id="preview" class="card" hidden>
          <p id="selection-label">${this.t('Ausgewählt · noch nicht übernommen', 'Selected · not yet applied')}</p><h2 class="title" id="preview-name"></h2><p id="preview-address"></p>
          <details id="map-details"><summary>${this.t('Kartenvorschau','Map preview')}</summary><div id="preview-map"></div></details><a id="map-link" target="_blank" rel="noopener noreferrer">${this.t('In Karten öffnen','Open in maps')}</a>
          <div class="row"><button id="confirm" class="primary"></button><button id="cancel">${this.t('Abbrechen','Cancel')}</button></div>
        </section>
        <section class="card">
          <p id="status"></p><h2 id="selected" class="title"></h2><p id="selected-address" class="muted"></p>
          <div class="row"><button id="start" class="primary">${this.t('Fahrt teilen','Share trip')}</button><button id="accept" hidden>${this.t('Neues Ziel übernehmen','Accept new destination')}</button><button id="finish">${this.t('Fahrt beenden','Finish trip')}</button></div>
          <div id="share" hidden><label for="share-url">${this.t('Freigabelink','Share link')}</label><input id="share-url" readonly><div class="row"><button id="copy">${this.t('Link kopieren','Copy link')}</button><button id="native-share">${this.t('Link teilen','Share link')}</button></div></div>
        </section>
      </main></ha-card>`;
    this.el('card-title').textContent = this.config?.title || 'Route Progress';
    this.el('search-form').onsubmit = e => { e.preventDefault(); clearTimeout(this.timer); this.search(); };
    this.el('query').oninput = () => {
      clearTimeout(this.timer);
      this.sequence++;
      this.message('');
      this.geoapifyResults = false;
      this.updateAttribution();
      this.el('results').replaceChildren();
      this.el('preview').hidden = true;
      this.preview = null;
      if (this.state) this.renderState(this.state);
      const q = this.el('query').value.trim();
      if (q.length >= 3 && (this.state?.search_enabled || /^https:\/\//i.test(q))) {
        this.timer = setTimeout(() => this.search(), 500);
      }
    };
    this.el('confirm').onclick = () => this.run('select', { target_id: this.preview.id });
    this.el('cancel').onclick = () => { this.preview = null; this.el('preview').hidden = true; this.renderState(this.state); this.el('query').focus(); };
    this.el('map-details').ontoggle = () => { if (this.el('map-details').open && this.preview) this.renderMap(this.preview); };
    for (const action of ['start', 'finish', 'accept']) this.el(action).onclick = () => this.run(action);
    this.el('copy').onclick = async () => {
      try { await navigator.clipboard.writeText(this.state.share_url); this.message(this.t('Link kopiert.', 'Link copied.')); }
      catch { this.el('share-url').select(); this.message(this.t('Bitte den markierten Link kopieren.', 'Please copy the selected link.')); }
    };
    this.el('native-share').hidden = !navigator.share;
    this.el('native-share').onclick = async () => {
      try { await navigator.share({ title: 'Route Progress', url: this.state.share_url }); }
      catch (e) { if (e.name !== 'AbortError') this.message(this.t('Bitte „Link kopieren“ verwenden.', 'Please use Copy link.'), true); }
    };
  }

  message(text, error = false) {
    this.el('message').textContent = text;
    this.el('message').className = error ? 'error' : '';
  }

  error(err) {
    const messages = {
      unauthorized: ['Keine Berechtigung für diese Fahrtsteuerung.', 'You do not have permission to control this trip.'],
      unsupported_link: ['Dieser Maps-Link enthält kein lesbares Ziel. Bitte einen Ortslink teilen oder nach der Adresse suchen.', 'This Maps link has no readable destination. Share a place link or search for its address.'],
      ambiguous_link: ['Der Link enthält mehrere mögliche Ziele. Bitte einen einzelnen Ort teilen.', 'The link contains multiple possible destinations. Please share a single place.'],
      invalid_api_key: ['Der Geoapify-Schlüssel wurde abgelehnt. Bitte in der Integration prüfen.', 'Geoapify rejected the API key. Check the integration settings.'],
      api_key_required: ['Für diese Suche wird ein Geoapify-Schlüssel benötigt.', 'This search needs a Geoapify API key.'],
      rate_limited: ['Zu viele Suchanfragen oder Kontingent erreicht. Bitte später erneut suchen.', 'Too many requests or quota reached. Please try again later.'],
      result_expired: ['Der Treffer ist abgelaufen. Bitte erneut suchen.', 'This result expired. Please search again.'],
      server_unavailable: ['Der Route-Progress-Server ist nicht erreichbar. Das gewählte Ziel bleibt gespeichert.', 'The Route Progress server is unavailable. Your selected destination remains saved.'],
      manual_disabled: ['Die manuelle Zielauswahl ist nicht aktiviert. Bitte die Integration nachkonfigurieren.', 'Manual destinations are disabled. Please reconfigure the integration.'],
      destination_required: ['Bitte zuerst ein Ziel auswählen.', 'Please select a destination first.'],
      invalid_query: ['Bitte mindestens drei Zeichen eingeben.', 'Please enter at least three characters.'],
    };
    const pair = messages[err.code] || ['Die Anfrage ist fehlgeschlagen. Bitte erneut versuchen.', 'The request failed. Please try again.'];
    this.message(this.t(...pair), true);
  }

  async refresh() {
    if (!this._hass || this.busy || this.refreshing) return;
    this.refreshing = true;
    const mutation = this.mutation;
    try {
      const state = await this.call('state');
      if (mutation === this.mutation && !this.busy) this.renderState(state);
    }
    catch (e) { this.error(e); }
    finally { this.refreshing = false; }
  }

  renderState(state) {
    this.state = state;
    this.updateAttribution();
    this.el('key-hint').hidden = state.search_enabled;
    this.el('selected').textContent = state.destination?.name || this.t('Noch kein Ziel gewählt', 'No destination selected');
    this.el('selected-address').textContent = state.destination?.address || '';
    this.el('finish').hidden = !state.active;
    const labels = {
      idle: [state.destination ? 'Ziel gespeichert · Freigabe noch nicht gestartet' : 'Ziel auswählen', state.destination ? 'Destination saved · sharing not started' : 'Choose a destination'], waiting_for_destination: ['Warten auf das Ziel', 'Waiting for destination'],
      confirming_destination: ['Ziel wird bestätigt', 'Confirming destination'], en_route: ['Freigabe aktiv', 'Sharing active'],
      destination_changed: ['Zieländerung bestätigen', 'Confirm destination change'], navigation_uncertain: ['Zieldaten unsicher', 'Destination uncertain'],
      arrived_followup: ['Angekommen', 'Arrived'], arrived: ['Angekommen', 'Arrived'], manually_finished: ['Fahrt beendet', 'Trip finished'], expired: ['Freigabe abgelaufen', 'Share expired'],
    };
    this.el('status').textContent = state.available ? this.t(...(labels[state.status] || [state.status, state.status])) : this.t('Server nicht erreichbar', 'Server unavailable');
    this.el('start').disabled = this.busy || !state.can_start || !!this.preview;
    this.el('start').hidden = state.active;
    this.el('query').disabled = this.busy;
    this.el('search').disabled = this.busy;
    this.el('cancel').disabled = this.busy;
    this.el('finish').disabled = this.busy || !state.active || !state.available;
    this.el('accept').hidden = !state.can_accept;
    this.el('accept').disabled = this.busy || !state.available;
    this.el('confirm').disabled = this.busy;
    this.el('confirm').textContent = state.active ? this.t('Fahrtziel ändern', 'Change trip destination') : this.t('Ziel übernehmen', 'Use destination');
    this.el('share').hidden = !state.share_url;
    this.el('share-url').value = state.share_url || '';
    this.el('zones').replaceChildren(...state.zones.map(zone => {
      const button = document.createElement('button');
      button.textContent = zone.name;
      const selected = this.preview || state.destination;
      button.setAttribute('aria-pressed', String(selected?.latitude === zone.latitude && selected?.longitude === zone.longitude));
      button.disabled = this.busy;
      button.onclick = () => this.showPreview(zone);
      return button;
    }));
  }

  updateAttribution() {
    this.el('attribution').hidden = !(this.geoapifyResults || this.state?.destination?.source === 'geoapify');
  }

  async search() {
    const sequence = ++this.sequence;
    if (this.el('query').value.trim().length < 3) { this.error({code:'invalid_query'}); return; }
    this.message(this.t('Suche …', 'Searching …'));
    try {
      const { results } = await this.call('search', { query: this.el('query').value.trim() });
      if (sequence !== this.sequence) return;
      this.el('results').replaceChildren(...results.map(result => {
        const button = document.createElement('button');
        button.className = 'result';
        const title = document.createElement('strong');
        title.textContent = result.name;
        const address = document.createElement('small');
        address.textContent = result.address || `${result.latitude.toFixed(5)}, ${result.longitude.toFixed(5)}`;
        button.append(title, address);
        button.onclick = () => this.showPreview(result);
        return button;
      }));
      this.geoapifyResults = results.some(r => r.source === 'geoapify');
      this.updateAttribution();
      this.message(results.length ? this.t('Bitte einen Treffer auswählen.', 'Please select a result.') : this.t('Keine Treffer. Versuche Ort und Straße genauer anzugeben.', 'No results. Try a more specific place or address.'));
    } catch (e) { if (sequence === this.sequence) this.error(e); }
  }

  showPreview(target) {
    if (this.busy) return;
    clearTimeout(this.timer);
    this.sequence++;
    this.preview = target;
    this.el('results').replaceChildren();
    this.message('');
    this.geoapifyResults = target.source === 'geoapify';
    this.updateAttribution();
    this.el('map-details').open = false;
    this.el('preview-map').replaceChildren();
    this.el('preview-name').textContent = target.name;
    this.el('preview-address').textContent = target.address || '';
    this.el('map-link').href = `https://www.openstreetmap.org/?${new URLSearchParams({ mlat: target.latitude, mlon: target.longitude })}#map=16/${target.latitude}/${target.longitude}`;
    this.renderState(this.state);
    this.el('preview').hidden = false;
    this.el('preview').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    this.el('confirm').focus({ preventScroll: true });
  }

  async renderMap(target) {
    // Use HA's map renderer instead of an external, possibly blocked iframe.
    const container = this.el('preview-map');
    try {
      const helpers = await window.loadCardHelpers();
      if (this.preview !== target || !this.el('map-details').open) return;
      const entityId = 'sensor.route_progress_preview';
      const map = helpers.createCardElement({ type: 'map', entities: [entityId], hours_to_show: 0, default_zoom: 14, aspect_ratio: '16:9' });
      const now = new Date().toISOString();
      const previewHass = { ...this._hass, states: { ...this._hass.states, [entityId]: {
        entity_id: entityId, state: target.name,
        attributes: { friendly_name: target.name, latitude: target.latitude, longitude: target.longitude, icon: 'mdi:map-marker' },
        last_changed: now, last_updated: now, context: { id: '', parent_id: null, user_id: null },
      } } };
      // Modern ha-map consumes Lit's states context instead of the parent's
      // hass property. Supply the same immutable preview to that subtree only.
      // Other HA contexts continue bubbling to the real dashboard provider.
      map.addEventListener('context-request', event => {
        if (event.context !== 'states') return;
        event.stopPropagation();
        event.callback(previewHass.states, () => {});
      });
      map.hass = previewHass;
      container.replaceChildren(map);
    } catch {
      if (this.preview === target) container.textContent = this.t('Vorschau nicht verfügbar. Bitte „In Karten öffnen“ verwenden.', 'Preview unavailable. Please use Open in maps.');
    }
  }

  async run(action, extra = {}) {
    if (this.busy) return;
    clearTimeout(this.timer);
    this.sequence++;
    this.busy = true;
    this.mutation++;
    this.renderState(this.state);
    this.message('');
    try {
      const state = await this.call(action, extra);
      if (action === 'select') {
        this.preview = null;
        this.el('preview').hidden = true;
        this.el('results').replaceChildren();
        this.el('query').value = '';
        this.geoapifyResults = false;
        this.message(this.t('Ziel übernommen.', 'Destination selected.'));
      }
      this.state = state;
    } catch (e) { this.error(e); }
    finally { this.busy = false; this.renderState(this.state); }
  }
}
if (!customElements.get('route-progress-card')) customElements.define('route-progress-card', RouteProgressCard);

window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === 'route-progress-card')) {
  window.customCards.push({ type: 'route-progress-card', name: 'Route Progress', preview: true,
    description: 'Zielsuche, Google-Maps-Links, HA-Zonen und Fahrtfreigabe / Destination search and trip sharing' });
}

class RouteProgressCardEditor extends HTMLElement {
  setConfig(config) {
    this.config = { ...config };
    if (!this.input) {
      const label = document.createElement('label');
      label.textContent = 'Titel / Title';
      label.style.cssText = 'display:block;padding:16px;font:inherit';
      this.input = document.createElement('input');
      this.input.style.cssText = 'display:block;width:100%;box-sizing:border-box;margin-top:8px;padding:12px;font:inherit';
      this.input.oninput = () => {
        const config = { ...this.config, title: this.input.value };
        this.config = config;
        this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
      };
      label.append(this.input);
      this.append(label);
    }
    this.input.value = this.config.title || '';
    this.input.placeholder = 'Route Progress';
  }
}
if (!customElements.get('route-progress-card-editor')) customElements.define('route-progress-card-editor', RouteProgressCardEditor);
