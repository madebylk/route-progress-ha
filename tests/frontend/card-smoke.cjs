// Run against `node tests/frontend/serve-preview.cjs`; uses the real card code.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({ headless: true, ...(process.env.ROUTE_PROGRESS_CHROMIUM ? { executablePath: process.env.ROUTE_PROGRESS_CHROMIUM } : {}) });
 try {
  const page = await browser.newPage({ viewport: { width: 420, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  // The map itself is an external service, not part of this deterministic test.
  await page.route('https://www.openstreetmap.org/**', route => route.fulfill({ body: '<p>Map preview</p>', contentType: 'text/html' }));
  await page.goto('http://127.0.0.1:8766');
  const card = page.locator('route-progress-card');
  await card.locator('#selected').waitFor();
  assert.equal(await card.locator('#start').isDisabled(), true);
  assert.equal(await card.locator('h1').count(), 0);
  assert.equal(await card.locator('#finish').isVisible(), false);
  await card.locator('#query').fill('Hamburg');
  await card.getByRole('button', { name: 'Hamburg Hauptbahnhof Hachmannplatz' }).waitFor();
  await card.locator('.result').click();
  assert.equal(await card.locator('#preview-name').innerText(), 'Hamburg Hauptbahnhof');
  assert.equal(await card.locator('.result').count(), 0, 'results collapse after selection');
  assert.equal(await card.locator('#message').innerText(), '');
  await card.locator('#map-details summary').click();
  await page.waitForFunction(() => window.mapTarget);
  assert.equal(await page.evaluate(() => window.mapTarget.attributes.latitude), 53.5528);
  assert.equal(await page.evaluate(() => window.mapTarget.attributes.longitude), 10.0067);
  assert.equal(await page.evaluate(() => window.legacyMapTarget.state), 'Hamburg Hauptbahnhof');
  assert.equal(await page.evaluate(() => window.mapTheme), 'test', 'unrelated HA contexts still bubble');
  assert.equal(await card.locator('test-ha-map').innerText(), 'Destination marker: Hamburg Hauptbahnhof');
  await card.locator('#map-details summary').click();
  await card.locator('#map-details summary').click();
  assert.equal(await card.locator('test-ha-map').innerText(), 'Destination marker: Hamburg Hauptbahnhof');
  assert.equal(await card.locator('iframe').count(), 0);
  assert.equal(await card.locator('#map-link').getAttribute('href').then(url => url.includes('53.5528')), true);
  await card.locator('#confirm').click();
  await card.locator('#start:not([disabled])').waitFor();
  assert.equal(await page.evaluate(() => window.requests.filter(r => r.action === 'start').length), 0);
  await card.locator('#start').click();
  await card.locator('#share:not([hidden])').waitFor();
  assert.equal(await card.locator('#share-url').inputValue(), 'https://example.com/t/test');
  await card.getByRole('button', { name: 'Zuhause', exact: true }).click();
  assert.equal(await card.getByRole('button', {name:'Zuhause',exact:true}).getAttribute('aria-pressed'), 'true');
  await card.locator('#map-details summary').click();
  await card.locator('test-ha-map').filter({hasText:'Destination marker: Zuhause'}).waitFor();
  assert.equal(await page.evaluate(() => window.mapTarget.attributes.latitude), 53.55);
  assert.equal(await page.evaluate(() => {
    let leaked = false;
    const event = new Event('context-request', {bubbles:true, composed:true});
    event.context = 'states';
    event.callback = states => { leaked = !!states['sensor.route_progress_preview']; };
    document.body.dispatchEvent(event);
    return leaked;
  }), false, 'preview state must remain local to its map');
  await card.locator('#map-details summary').click();
  await page.evaluate(() => { window.loadCardHelpers = async () => { throw Error('unavailable'); }; });
  await card.locator('#map-details summary').click();
  await card.locator('#preview-map').filter({hasText:'Vorschau nicht verfügbar'}).waitFor();
  assert.equal(await card.locator('#confirm').innerText(), 'Fahrtziel ändern');
  await card.locator('#confirm').click();
  await card.locator('#selected').filter({ hasText: 'Zuhause' }).waitFor();
  await card.locator('#query').fill('error');
  await card.locator('#message').filter({ hasText: 'abgelehnt' }).waitFor();
  await card.locator('#query').fill('slow');
  await page.waitForFunction(() => window.requests.some(r => r.query === 'slow'));
  await card.locator('#query').fill('none');
  await card.locator('#message').filter({ hasText: 'Keine Treffer' }).waitFor();
  await page.waitForTimeout(1000);
  assert.equal(await card.locator('.result').count(), 0, 'stale request replaced results');
  await card.locator('#finish').click();
  await card.locator('#status').filter({ hasText: 'Fahrt beendet' }).waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'mobile overflow');
  if (process.env.ROUTE_PROGRESS_SCREENSHOT) await page.screenshot({ path: process.env.ROUTE_PROGRESS_SCREENSHOT, fullPage: true });
  const editorOK = await page.evaluate(() => {
    const editor = customElements.get('route-progress-card').getConfigElement();
    editor.setConfig({type:'custom:route-progress-card',title:'Test'});
    return editor.querySelector('input').value === 'Test' && window.customCards.some(c => c.type === 'route-progress-card');
  });
  assert.equal(editorOK, true);
  assert.deepEqual(errors, []);
  for (const width of [320, 420, 800]) {
    await page.setViewportSize({width, height:1000});
    await card.getByRole('button', {name:'Zuhause',exact:true}).click();
    assert.equal(await card.locator('#start').isDisabled(), true, 'pending preview must not start the previous target');
    assert.equal(await page.evaluate(() => {
      const card = document.querySelector('route-progress-card');
      return card.shadowRoot.querySelector('ha-card').scrollWidth > card.clientWidth;
    }), false, `card overflow at ${width}px`);
  }
  await page.setViewportSize({width:420,height:1000});
  if (process.env.ROUTE_PROGRESS_SCREENSHOT) await page.screenshot({path:process.env.ROUTE_PROGRESS_SCREENSHOT.replace('.png','-selection.png'),fullPage:true});
  await page.evaluate(() => {
    document.body.style.setProperty('--card-background-color','#1c1c1c');
    document.body.style.setProperty('--primary-text-color','#eeeeee');
    document.body.style.setProperty('--secondary-text-color','#bbbbbb');
    document.body.style.setProperty('--divider-color','#444444');
  });
  if (process.env.ROUTE_PROGRESS_SCREENSHOT) await page.screenshot({path:process.env.ROUTE_PROGRESS_SCREENSHOT.replace('.png','-dark.png'),fullPage:true});
  console.log('Card browser smoke passed: search, preview, selection, start, change, errors, stale results, finish, mobile layout, editor.');
 } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
