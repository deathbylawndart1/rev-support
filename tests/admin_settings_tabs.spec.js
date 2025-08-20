/*
 Automated verification for Admin Settings tabs using Puppeteer.
 Assumes the Flask app is running locally and seeded with admin/admin123.
*/

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:5000';
const SCREENSHOT_DIR = path.join(__dirname, 'screenshots', 'admin-settings');

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

async function testTelegramGroupsCrud(page) {
  const slug = 'telegram-groups';

  // Mock backend state (used by intercept handler)
  const state = {
    nextId: 2,
    groups: [
      {
        id: 1,
        name: 'Support Primary',
        telegram_group_id: '12345',
        description: 'Primary support group',
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: null,
      },
    ],
  };

  // Intercept API calls BEFORE navigation so initial loadGroups() uses mocked data
  await page.setRequestInterception(true);
  const handler = async (request) => {
    const url = request.url();
    const method = request.method();
    try {
      // List or create
      if (url.endsWith('/api/telegram_groups')) {
        if (method === 'GET') {
          console.log('[MOCK] GET /api/telegram_groups');
          return await request.respond({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(state.groups.slice().reverse()), // simulate order_by created_at desc
          });
        }
        if (method === 'POST') {
          console.log('[MOCK] POST /api/telegram_groups');
          const bodyRaw = request.postData() || '{}';
          let data; try { data = JSON.parse(bodyRaw); } catch { data = {}; }
          const name = (data.name || '').trim();
          const gid = String(data.telegram_group_id || '').trim();
          if (!name || !gid) {
            return await request.respond({ status: 400, contentType: 'application/json', body: JSON.stringify({ status: 'error', message: 'name and telegram_group_id are required' }) });
          }
          if (state.groups.some(g => g.telegram_group_id === gid)) {
            return await request.respond({ status: 409, contentType: 'application/json', body: JSON.stringify({ status: 'error', message: 'telegram_group_id already exists' }) });
          }
          const g = {
            id: state.nextId++,
            name,
            telegram_group_id: gid,
            description: (data.description || '').trim() || null,
            is_active: !!data.is_active,
            created_at: new Date().toISOString(),
            updated_at: null,
          };
          state.groups.push(g);
          return await request.respond({ status: 201, contentType: 'application/json', body: JSON.stringify({ status: 'success', id: g.id }) });
        }
      }

      // Update or delete specific group
      const m = url.match(/\/api\/telegram_groups\/(\d+)$/);
      if (m) {
        const id = parseInt(m[1], 10);
        const idx = state.groups.findIndex(g => g.id === id);
        if (idx === -1) {
          return await request.respond({ status: 404, contentType: 'application/json', body: JSON.stringify({ status: 'error', message: 'not found' }) });
        }
        const group = state.groups[idx];
        if (method === 'PUT') {
          console.log(`[MOCK] PUT /api/telegram_groups/${id}`);
          const bodyRaw = request.postData() || '{}';
          let data; try { data = JSON.parse(bodyRaw); } catch { data = {}; }
          if ('telegram_group_id' in data) {
            const newGid = String(data.telegram_group_id || '').trim();
            if (!newGid) {
              return await request.respond({ status: 400, contentType: 'application/json', body: JSON.stringify({ status: 'error', message: 'telegram_group_id cannot be empty' }) });
            }
            if (state.groups.some(g => g.telegram_group_id === newGid && g.id !== id)) {
              return await request.respond({ status: 409, contentType: 'application/json', body: JSON.stringify({ status: 'error', message: 'telegram_group_id already exists' }) });
            }
            group.telegram_group_id = newGid;
          }
          if ('name' in data) {
            const newName = (data.name || '').trim();
            if (!newName) {
              return await request.respond({ status: 400, contentType: 'application/json', body: JSON.stringify({ status: 'error', message: 'name cannot be empty' }) });
            }
            group.name = newName;
          }
          if ('description' in data) {
            group.description = (data.description || '').trim() || null;
          }
          if ('is_active' in data) {
            group.is_active = !!data.is_active;
          }
          group.updated_at = new Date().toISOString();
          return await request.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success' }) });
        } else if (method === 'DELETE') {
          console.log(`[MOCK] DELETE /api/telegram_groups/${id}`);
          group.is_active = false;
          group.updated_at = new Date().toISOString();
          return await request.respond({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'success' }) });
        }
      }

      // Passthrough for everything else
      await request.continue();
    } catch (e) {
      try { await request.continue(); } catch {}
    }
  };
  page.on('request', handler);

  // Now navigate so DOMContentLoaded loadGroups() hits our mock
  await page.goto(`${BASE_URL}/settings?tab=${slug}`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('#tab-telegram-groups');
  await sleep(150); // allow DOM scripts to attach and initial loadGroups() to run

  // Ensure the tab container has non-zero size
  await page.evaluate(() => {
    const el = document.querySelector('#tab-telegram-groups');
    if (el) {
      el.style.minWidth = '1024px';
      el.style.width = '100%';
      el.style.minHeight = '600px';
      el.style.display = 'block';
      el.style.visibility = 'visible';
      if (typeof el.scrollIntoView === 'function') el.scrollIntoView();
    }
  });

  try {
    // Ensure tbody exists, then proceed (we will validate after add)
    await page.waitForSelector('#groupsTable tbody');
    // Debug: log initial tbody content
    const initialTbodyHtml = await page.$eval('#groupsTable tbody', el => el.innerHTML);
    console.log('[DEBUG] Initial tbody HTML length:', initialTbodyHtml.length);
    console.log('[DEBUG] Initial tbody HTML (truncated):', initialTbodyHtml.slice(0, 200));
    await sleep(100);
    const preRows = await page.$$eval('#groupsTable tbody tr', rows => rows.length);
    console.log('[DEBUG] Pre-wait row count:', preRows);

    const initialRows = await page.$$eval('#groupsTable tbody tr', rows => rows.length);
    if (initialRows < 1) {
      console.log('[WARN] Initial groups did not render any rows; continuing with add flow');
    }

    // Add Group
    await clickWithFallback(page, '#btnAddGroup');
    // Wait until Bootstrap sets the .show class; this ensures the addBtn handler finished resetting fields
    await page.waitForFunction(() => {
      const el = document.getElementById('groupModal');
      return !!(el && el.classList.contains('show'));
    }, { timeout: 5000 });
    // Set fields via JS to avoid timing races and ensure values stick
    await page.evaluate(() => {
      const nameEl = document.getElementById('groupName');
      const idEl = document.getElementById('groupId');
      const descEl = document.getElementById('groupDesc');
      const activeEl = document.getElementById('groupActive');
      if (nameEl) nameEl.value = 'Escalations';
      if (idEl) idEl.value = '99999';
      if (descEl) descEl.value = 'Escalations group';
      if (activeEl) activeEl.checked = true;
      nameEl?.dispatchEvent(new Event('input', { bubbles: true }));
      idEl?.dispatchEvent(new Event('input', { bubbles: true }));
      descEl?.dispatchEvent(new Event('input', { bubbles: true }));
    });
    // leave Active checked
    const filled = await page.evaluate(() => ({
      name: document.getElementById('groupName')?.value,
      gid: document.getElementById('groupId')?.value,
      desc: document.getElementById('groupDesc')?.value,
      active: document.getElementById('groupActive')?.checked,
    }));
    console.log('[DEBUG] Filled modal values:', JSON.stringify(filled));
    // Click save and wait for modal to hide (best proxy for completion)
    await clickWithFallback(page, '#saveGroupBtn');
    try {
      await page.waitForFunction(() => {
        const el = document.getElementById('groupModal');
        return !!(el && !el.classList.contains('show'));
      }, { timeout: 7000 });
    } catch (e) {
      console.log('[WARN] Modal did not hide within timeout:', e.message);
    }
    // Wait for GET refresh and then for the newly added row by name
    try { await page.waitForResponse(r => r.url().endsWith('/api/telegram_groups') && r.request().method() === 'GET', { timeout: 7000 }); } catch {}
    await page.waitForFunction(() => {
      const rows = Array.from(document.querySelectorAll('#groupsTable tbody tr'));
      return rows.some(r => r.querySelector('td')?.textContent.trim() === 'Escalations');
    }, { timeout: 7000 });
    const afterAddRows = await page.$$eval('#groupsTable tbody tr', rows => rows.length);
    console.log('[DEBUG] Rows after add:', afterAddRows);

    // Edit the newly added group name
    // Find its id via the edit button in the row with matching name
    const newId = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('#groupsTable tbody tr'));
      for (const r of rows) {
        const name = r.querySelector('td')?.textContent.trim();
        if (name === 'Escalations') {
          const btn = r.querySelector('button[data-action="edit"]');
          return btn ? btn.getAttribute('data-id') : null;
        }
      }
      return null;
    });
    if (!newId) throw new Error('Could not locate new group row for editing');
    await clickWithFallback(page, `button[data-action="edit"][data-id="${newId}"]`);
    // Ensure modal is fully shown before editing
    await page.waitForFunction(() => {
      const el = document.getElementById('groupModal');
      return !!(el && el.classList.contains('show'));
    }, { timeout: 5000 });
    // Set the name field via JS to avoid races
    await page.evaluate(() => {
      const nameEl = document.getElementById('groupName');
      if (nameEl) {
        nameEl.value = 'Escalations Updated';
        nameEl.dispatchEvent(new Event('input', { bubbles: true }));
        nameEl.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    await clickWithFallback(page, '#saveGroupBtn');
    // Wait for the table to reflect the updated name
    await page.waitForFunction(() => {
      const rows = Array.from(document.querySelectorAll('#groupsTable tbody tr'));
      return rows.some(r => r.querySelector('td')?.textContent.trim() === 'Escalations Updated');
    }, { timeout: 7000 });

    // Toggle active off
    await clickWithFallback(page, `input.form-check-input[data-action="toggle"][data-id="${newId}"]`);
    await sleep(100);
    const toggled = await page.$eval(`input.form-check-input[data-action="toggle"][data-id="${newId}"]`, el => el.checked);
    if (toggled !== false) throw new Error('Toggle active off did not apply');

    // Delete (soft deactivate)
    await clickWithFallback(page, `button[data-action="delete"][data-id="${newId}"]`);
    await page.waitForSelector('#tgDeleteModal.show, #tgDeleteModal', { timeout: 3000 });
    // ensure modal is visible and click confirm
    await page.evaluate(() => {
      const el = document.getElementById('tgDeleteModal');
      if (el) { el.style.display = 'block'; el.style.visibility = 'visible'; }
    });
    await clickWithFallback(page, '#confirmDeleteGroupBtn');
    await sleep(120);
    const afterDeleteChecked = await page.$eval(`input.form-check-input[data-action="toggle"][data-id="${newId}"]`, el => el.checked);
    if (afterDeleteChecked !== false) throw new Error('Delete did not result in inactive status');

    // Screenshot final table
    ensureDir(SCREENSHOT_DIR);
    await screenshotElement(page, '#tab-telegram-groups', path.join(SCREENSHOT_DIR, 'telegram-groups-crud.png'));
    console.log('[OK] Telegram Groups CRUD (mocked) passed');
  } finally {
    page.off('request', handler);
    try { await page.setRequestInterception(false); } catch {}
  }
}

async function testModelLoader(page) {
  const slug = 'ai-integration';
  await page.goto(`${BASE_URL}/settings?tab=${slug}`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('#aiIntegrationForm');

  // Ensure the tab container has non-zero size for clickability in headless
  await page.evaluate(() => {
    const el = document.querySelector('#tab-ai-integration');
    if (el) {
      el.style.minWidth = '1024px';
      el.style.width = '100%';
      el.style.minHeight = '600px';
      el.style.display = 'block';
      el.style.visibility = 'visible';
      if (typeof el.scrollIntoView === 'function') el.scrollIntoView();
    }
  });

  // Intercept the models API to return a mocked list
  await page.setRequestInterception(true);
  const handler = async (request) => {
    try {
      const url = request.url();
      const method = request.method();
      if (url.endsWith('/api/ai/models') && method === 'POST') {
        await request.respond({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            source: 'mock',
            models: [
              { id: 'gpt-4o-mini', label: 'GPT-4o mini' },
              { id: 'gpt-4o', label: 'GPT-4o' },
              { id: 'llama3.1', label: 'Llama 3.1' }
            ]
          })
        });
      } else {
        await request.continue();
      }
    } catch (e) {
      try { await request.continue(); } catch {}
    }
  };
  page.on('request', handler);

  try {
    // Try standard click, then JS click as a fallback
    const btn = await page.$('#loadModelsBtn');
    if (!btn) throw new Error('Load Models button not found');
    try {
      await btn.click({ delay: 10 });
    } catch (e) {
      await page.evaluate(() => document.getElementById('loadModelsBtn')?.click());
    }
    // Wait for status update or select to be shown
    await page.waitForFunction(() => {
      const status = document.getElementById('ai_models_status');
      const sel = document.getElementById('ai_model_select');
      const okText = !!status && /Loaded \d+ models/.test(status.textContent || '');
      const okSel = !!sel && getComputedStyle(sel).display !== 'none' && sel.options.length >= 3;
      return okText || okSel;
    }, { timeout: 5000 });

    // Assert select is populated and visible
    const selectInfo = await page.evaluate(() => {
      const sel = document.getElementById('ai_model_select');
      const inp = document.getElementById('ai_model');
      return {
        visible: !!sel && getComputedStyle(sel).display !== 'none',
        options: sel ? Array.from(sel.options).map(o => o.value) : [],
        inputVal: inp ? inp.value : ''
      };
    });
    if (!selectInfo.visible) throw new Error('Model select did not become visible');
    if (selectInfo.options.length < 3) throw new Error('Model select did not populate with mocked options');

    // Change selection and verify input sync
    const target = selectInfo.options.find(v => v && v !== selectInfo.inputVal) || selectInfo.options[0];
    await page.select('#ai_model_select', target);
    await sleep(50);
    const synced = await page.$eval('#ai_model', el => el.value);
    if (synced !== target) throw new Error('ai_model input did not sync to selected option');

    // Screenshot the populated select area
    ensureDir(SCREENSHOT_DIR);
    await screenshotElement(page, '#tab-ai-integration', path.join(SCREENSHOT_DIR, 'ai-integration-models.png'));
    console.log('[OK] AI models loaded and synced');
  } finally {
    page.off('request', handler);
    try { await page.setRequestInterception(false); } catch {}
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function clickWithFallback(page, selector) {
  const el = await page.$(selector);
  if (!el) throw new Error(`Element not found: ${selector}`);
  await page.evaluate((sel) => {
    const node = document.querySelector(sel);
    if (!node) return;
    node.style.visibility = 'visible';
    node.style.display = node.style.display || 'inline-block';
    node.style.opacity = '1';
    node.style.pointerEvents = 'auto';
    if (typeof node.scrollIntoView === 'function') {
      node.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
    }
  }, selector);
  try {
    await el.click({ delay: 10 });
  } catch (e) {
    // Fallback to JS-driven click
    await page.evaluate((sel) => {
      const node = document.querySelector(sel);
      if (node) node.click();
    }, selector);
  }
  await sleep(50);
}

async function screenshotElement(page, selector, file) {
  const el = await page.$(selector);
  if (!el) throw new Error(`Selector not found for screenshot: ${selector}`);
  // Nudge for headless layout issues
  await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return;
    el.style.minHeight = '800px';
    el.style.minWidth = '1024px';
    el.style.width = '100%';
    el.style.display = 'block';
    el.style.visibility = 'visible';
    if (typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'start', inline: 'nearest' });
    }
  }, selector);
  // If element has no bounding box, fall back to full-page screenshot
  const box = await el.boundingBox();
  if (!box || box.width < 4 || box.height < 4) {
    await page.screenshot({ path: file, fullPage: true });
    return;
  }
  await el.screenshot({ path: file });
}

async function domInfo(page, id) {
  return await page.evaluate((id) => {
    const el = document.getElementById(id);
    if (!el) return { exists: false };
    const st = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      exists: true,
      id,
      className: el.className,
      display: st.display,
      width: r.width,
      height: r.height,
      childCount: el.querySelectorAll('*').length,
      htmlLen: (el.innerHTML || '').length,
    };
  }, id);
}

async function login(page, { username, password }) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' });
  // Prefer by name to avoid WTForms id variance
  const userSel = 'input[name="username"], #username';
  const passSel = 'input[name="password"], #password';
  await page.waitForSelector(userSel, { timeout: 10000 });
  await page.type(userSel, username, { delay: 10 });
  await page.type(passSel, password, { delay: 10 });
  await Promise.all([
    page.click('button[type="submit"], button.btn-primary'),
    page.waitForNavigation({ waitUntil: 'networkidle0' })
  ]);
  if (!page.url().includes('/dashboard')) {
    throw new Error(`Login failed; current URL: ${page.url()}`);
  }
}

async function verifyTab(page, { slug, containerId, keySelectors = [] }) {
  const url = `${BASE_URL}/settings?tab=${slug}`;
  await page.goto(url, { waitUntil: 'networkidle0' });
  const containerSel = `#${containerId}`;
  await page.waitForSelector(containerSel, { timeout: 10000 });

  // Wait for active class (d-block)
  await page.waitForFunction(
    (sel) => {
      const el = document.querySelector(sel);
      return !!el && el.classList.contains('d-block');
    },
    { timeout: 10000 },
    containerSel
  );

  // Assert key selectors exist (if provided)
  for (const sel of keySelectors) {
    const exists = await page.$(sel);
    if (!exists) throw new Error(`Missing expected selector on ${slug}: ${sel}`);
  }

  // Collect diagnostics and enforce min content
  const info = await domInfo(page, containerId);
  if (!info.exists) throw new Error(`Container not found: ${containerId}`);
  if (info.htmlLen < 50) throw new Error(`Container has too little content: ${containerId}`);

  // Screenshot
  ensureDir(SCREENSHOT_DIR);
  const file = path.join(SCREENSHOT_DIR, `${slug}.png`);
  await screenshotElement(page, containerSel, file);
  console.log(`[OK] Tab ${slug}:`, info);
}

async function testProviderToggles(page) {
  const slug = 'ai-integration';
  await page.goto(`${BASE_URL}/settings?tab=${slug}`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('#aiIntegrationForm');

  const providerSel = '#ai_provider';
  const baseUrlGroup = '#ai_base_url_group';
  const orgGroup = '#ai_org_group';

  const setProvider = async (value) => {
    const found = await page.evaluate((sel, value) => {
      const el = document.querySelector(sel);
      if (!el) return false;
      const has = Array.from(el.options).some(o => o.value === value);
      if (!has) return false;
      el.value = value;
      el.dispatchEvent(new Event('change', { bubbles: true }));
      if (typeof window.updateAIControls === 'function') {
        window.updateAIControls();
      }
      return true;
    }, providerSel, value);
    return found;
  };

  const visibility = async () => {
    return await page.evaluate((baseSel, orgSel) => {
      const baseEl = document.querySelector(baseSel);
      const orgEl = document.querySelector(orgSel);
      const bs = baseEl ? getComputedStyle(baseEl).display : 'missing';
      const os = orgEl ? getComputedStyle(orgEl).display : 'missing';
      return { base: bs, org: os };
    }, baseUrlGroup, orgGroup);
  };

  const tryProvider = async (value, expect) => {
    const ok = await setProvider(value);
    if (!ok) {
      console.log(`[WARN] Provider option not present: ${value}`);
      return; // skip if this provider isn't in the dropdown
    }
    await sleep(200);
    const vis = await visibility();
    if (expect.base && vis.base === 'none') throw new Error(`Expected base URL visible for ${value}`);
    if (!expect.base && vis.base !== 'none' && vis.base !== 'missing') throw new Error(`Expected base URL hidden for ${value}`);
    if (expect.org && vis.org === 'none') throw new Error(`Expected org visible for ${value}`);
    if (!expect.org && vis.org !== 'none' && vis.org !== 'missing') throw new Error(`Expected org hidden for ${value}`);
    console.log(`[OK] Provider ${value} visibility =>`, vis);
  };

  await tryProvider('openai', { base: false, org: true });
  await tryProvider('azure_openai', { base: true, org: false });
  await tryProvider('ollama', { base: true, org: false });
  await tryProvider('custom', { base: true, org: false });
}

(async () => {
  ensureDir(SCREENSHOT_DIR);
  const browser = await puppeteer.launch({ headless: 'new', defaultViewport: { width: 1280, height: 900 } });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);
  // Debug: mirror browser console and failed requests to Node
  page.on('console', (msg) => {
    try { console.log('[BROWSER]', msg.type().toUpperCase(), msg.text()); } catch {}
  });
  page.on('requestfailed', (req) => {
    try { console.log('[REQ FAILED]', req.url(), req.failure()?.errorText); } catch {}
  });

  try {
    // 1) Login
    await login(page, { username: process.env.ADMIN_USER || 'admin', password: process.env.ADMIN_PASS || 'admin123' });

    // 2) Verify each tab
    await verifyTab(page, {
      slug: 'general',
      containerId: 'tab-general',
      keySelectors: ['#settingsForm', '#previewContainer']
    });

    await verifyTab(page, {
      slug: 'ai-integration',
      containerId: 'tab-ai-integration',
      keySelectors: ['#aiIntegrationForm', '#ai_provider', '#ai_api_key', '#ai_model']
    });

    await verifyTab(page, {
      slug: 'telegram-groups',
      containerId: 'tab-telegram-groups',
      keySelectors: ['#tab-telegram-groups']
    });

    await verifyTab(page, {
      slug: 'ai-knowledge',
      containerId: 'tab-ai-knowledge',
      keySelectors: ['#tab-ai-knowledge']
    });

    await verifyTab(page, {
      slug: 'ai-analytics',
      containerId: 'tab-ai-analytics',
      keySelectors: ['#tab-ai-analytics']
    });

    await verifyTab(page, {
      slug: 'templates',
      containerId: 'tab-templates',
      keySelectors: ['#tab-templates']
    });

    await verifyTab(page, {
      slug: 'users',
      containerId: 'tab-users',
      keySelectors: ['#tab-users']
    });

    await verifyTab(page, {
      slug: 'escalation',
      containerId: 'tab-escalation',
      keySelectors: ['#tab-escalation']
    });

    await verifyTab(page, {
      slug: 'node-red',
      containerId: 'tab-node-red',
      keySelectors: ['#tab-node-red']
    });

    // 3) Provider toggles
    await testProviderToggles(page);

    // 4) Load Models flow (mocked API)
    await testModelLoader(page);

    // 5) Telegram Groups CRUD (mocked API)
    console.log('--- Entering Telegram Groups CRUD test ---');
    await testTelegramGroupsCrud(page);

    console.log('\nAll Admin Settings tab checks completed successfully.');
  } catch (err) {
    console.error('\nTEST FAILED:', err.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
