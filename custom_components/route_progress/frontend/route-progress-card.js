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
  getCardSize() { return 9; }
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
        :host{display:block;background:var(--primary-background-color);color:var(--primary-text-color);font:16px var(--paper-font-body1_-_font-family, sans-serif)}
        *{box-sizing:border-box}header{padding:20px 20px 0}
        header strong{font-size:20px}main{padding:20px}h1{font-size:24px;margin:0 0 8px}h2{font-size:18px;margin-top:28px}
        p{line-height:1.5;color:var(--secondary-text-color)}label{display:block;margin:24px 0 8px;font-weight:600}.search{display:flex;gap:8px}
        input{min-width:0;flex:1;font:inherit;padding:14px;border-radius:12px;border:1px solid var(--divider-color);background:var(--card-background-color);color:inherit}
        button{font:inherit;cursor:pointer;border:1px solid var(--divider-color);border-radius:12px;padding:12px 16px;background:var(--card-background-color);color:inherit;min-height:44px}
        button:hover{border-color:var(--primary-color)}button:focus-visible,input:focus-visible,a:focus-visible{outline:3px solid var(--primary-color);outline-offset:3px}button:disabled{opacity:.5;cursor:default}
        .primary{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:transparent}.row{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
        .result{display:block;text-align:left;width:100%;margin-top:8px}.result small{display:block;color:var(--secondary-text-color);margin-top:5px;line-height:1.4}
        section.card{padding:20px;margin-top:24px;border:1px solid var(--divider-color);border-radius:16px;background:var(--card-background-color)}
        iframe{width:100%;height:210px;border:0;border-radius:10px;margin:14px 0}.muted{font-size:13px;color:var(--secondary-text-color)}
        a{color:var(--primary-color)}#message{white-space:pre-wrap}#message.error{color:var(--error-color,#b3261e)}[hidden]{display:none!important}
        #share-url{width:100%;margin-top:12px}#status{font-weight:600}.title{margin:0}#attribution{font-size:12px;margin-top:12px}
        @media(max-width:480px){main{margin:22px auto;padding:0 14px 32px}.search{flex-wrap:wrap}.search input{flex-basis:100%}.search button{width:100%}}
      </style>
      <ha-card><header><strong id="card-title"></strong></header>
      <main>
        <h1>${this.t('Wohin geht’s?', 'Where are you going?')}</h1>
        <p>${this.t('Suche dein Ziel, füge einen Google-Maps-Link ein oder wähle eine HA-Zone.', 'Search for a destination, paste a Google Maps link or choose a HA zone.')}</p>
        <label for="query">${this.t('Ort, Adresse oder Google-Maps-Link', 'Place, address or Google Maps link')}</label>
        <form id="search-form" class="search"><input id="query" type="text" maxlength="4096" autocomplete="off" placeholder="${this.t('Zum Beispiel: Hamburg Hauptbahnhof','For example: Hamburg Central Station')}"><button id="search" type="submit">${this.t('Suchen','Search')}</button></form>
        <p id="key-hint" class="muted" hidden>${this.t('Für die Adresssuche bitte einen Geoapify-Schlüssel in der Integration hinterlegen. HA-Zonen und Maps-Links mit Zielkoordinaten funktionieren ohne Schlüssel.', 'Configure a Geoapify key in the integration for address search. HA zones and Maps links containing destination coordinates work without a key.')}</p>
        <p id="message" role="status" aria-live="polite"></p>
        <div id="results" aria-label="${this.t('Suchergebnisse','Search results')}"></div>
        <div id="attribution" hidden>Powered by <a href="https://www.geoapify.com/" target="_blank" rel="noopener noreferrer">Geoapify</a> · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap contributors</a></div>
        <section><h2>${this.t('HA-Zonen','HA zones')}</h2><div id="zones" class="row"></div></section>
        <section id="preview" class="card" hidden>
          <h2 class="title" id="preview-name"></h2><p id="preview-address"></p>
          <div id="preview-map"></div><p class="muted" id="preview-coordinates"></p>
          <div class="row"><button id="confirm" class="primary"></button><button id="cancel">${this.t('Abbrechen','Cancel')}</button></div>
        </section>
        <section class="card">
          <p id="status"></p><h2 id="selected" class="title"></h2>
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
      const q = this.el('query').value.trim();
      if (q.length >= 3 && (this.state?.search_enabled || /^https:\/\//i.test(q))) {
        this.timer = setTimeout(() => this.search(), 500);
      }
    };
    this.el('confirm').onclick = () => this.run('select', { target_id: this.preview.id });
    this.el('cancel').onclick = () => { this.preview = null; this.el('preview').hidden = true; };
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
      unauthorized: ['Keine Berechtigung f�r diese Fahrtsteuerung.', 'You do not have permission to control this trip.'],
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
    const labels = {
      idle: ['Bereit', 'Ready'], waiting_for_destination: ['Warten auf das Ziel', 'Waiting for destination'],
      confirming_destination: ['Ziel wird bestätigt', 'Confirming destination'], en_route: ['Unterwegs', 'En route'],
      destination_changed: ['Zieländerung bestätigen', 'Confirm destination change'], navigation_uncertain: ['Zieldaten unsicher', 'Destination uncertain'],
      arrived_followup: ['Angekommen', 'Arrived'], arrived: ['Angekommen', 'Arrived'], manually_finished: ['Fahrt beendet', 'Trip finished'], expired: ['Freigabe abgelaufen', 'Share expired'],
    };
    this.el('status').textContent = state.available ? this.t(...(labels[state.status] || [state.status, state.status])) : this.t('Server nicht erreichbar', 'Server unavailable');
    this.el('start').disabled = this.busy || !state.can_start;
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
    this.preview = target;
    this.el('preview-name').textContent = target.name;
    this.el('preview-address').textContent = target.address || '';
    this.el('preview-coordinates').textContent = `${target.latitude.toFixed(5)}, ${target.longitude.toFixed(5)}`;
    const frame = document.createElement('iframe');
    frame.title = this.t('Ziel auf der Karte', 'Destination on map');
    frame.referrerPolicy = 'no-referrer';
    frame.loading = 'lazy';
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin');
    const lat = target.latitude, lon = target.longitude;
    const bbox = [Math.max(-180, lon - .012), Math.max(-90, lat - .008), Math.min(180, lon + .012), Math.min(90, lat + .008)].join(',');
    frame.src = `https://www.openstreetmap.org/export/embed.html?${new URLSearchParams({ bbox, layer: 'mapnik', marker: `${lat},${lon}` })}`;
    this.el('preview-map').replaceChildren(frame);
    this.el('preview').hidden = false;
    this.el('preview').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    this.el('confirm').focus({ preventScroll: true });
  }

  async run(action, extra = {}) {
    if (this.busy) return;
    this.busy = true;
    this.mutation++;
    this.renderState(this.state);
    this.message('');
    try {
      const state = await this.call(action, extra);
      if (action === 'select') {
        this.preview = null;
        this.el('preview').hidden = true;
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
