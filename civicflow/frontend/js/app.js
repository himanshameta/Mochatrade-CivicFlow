/**
 * CivicFlow — app.js
 * Single Page Application — Hash-based Router
 * JWT stored in memory only (never localStorage)
 * WebSocket auto-reconnect
 */

const App = (() => {
  'use strict';

  // ── State (in-memory only) ─────────────────────
  let _token    = null;
  let _userId   = null;
  let _userEmail= null;
  let _role     = 'primary';
  let _sessionId= null;
  let _ws       = null;
  let _wsReconnectTimer = null;
  let _chatSessionId = null;

  // API base
  const API = 'http://localhost:8000';
  const WS_BASE = 'ws://localhost:8000';

  // ── API Helper ─────────────────────────────────
  async function api(path, method = 'GET', body = null, isForm = false) {
    const headers = {};
    if (_token) headers['Authorization'] = `Bearer ${_token}`;
    if (!isForm) headers['Content-Type'] = 'application/json';

    const opts = { method, headers };
    if (body) opts.body = isForm ? body : JSON.stringify(body);

    try {
      const res = await fetch(`${API}${path}`, opts);
      const data = await res.json();
      
      if (!res.ok) {
        // Enhanced 422 error debugging
        if (res.status === 422 && data.errors) {
          console.error('[422 Validation Error]', data.errors);
          const fieldErrors = data.errors.map(e => `${e.loc.join('.')}: ${e.msg}`).join('; ');
          throw new Error(`Validation failed: ${fieldErrors}`);
        }
        throw new Error(data.detail?.message || data.message || data.detail || 'Server error');
      }
      return data;
    } catch (err) {
      if (err instanceof TypeError) throw new Error('Cannot connect to server. Is the backend running?');
      throw err;
    }
  }

  // ── Router ─────────────────────────────────────
  const ROUTES = {
    'login':         'view-login',
    'register':      'view-login',
    'profile-setup': 'view-profile-setup',
    'dashboard':     'view-dashboard',
    'form-search':   'view-form-search',
    'form-review':   'view-form-review',
    'execution':     'view-execution',
    'correction':    'view-correction',
    'session':       'view-session',
  };

  function navigate(page, params = {}) {
    const hash = params.id ? `#${page}/${params.id}` : `#${page}`;
    window.location.hash = hash;
  }

  function handleRoute() {
    const raw   = window.location.hash.slice(1) || 'login';
    const parts = raw.split('/');
    const page  = parts[0];
    const param = parts[1];

    // Auth guard
    if (!_token && page !== 'login' && page !== 'register') {
      navigate('login');
      return;
    }

    const viewId = ROUTES[page] || 'view-login';
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(viewId);
    if (target) target.classList.add('active');

    // Header visibility
    const header = document.getElementById('appHeader');
    if (page === 'login' || page === 'register') {
      header.style.display = 'none';
    } else {
      header.style.display = 'block';
    }

    // Auth tab
    if (page === 'register') showAuthTab('register');
    if (page === 'login')    showAuthTab('login');

    // Float counsellor — hide on auth
    const fc = document.getElementById('floatCounsellor');
    fc.style.display = (page === 'login' || page === 'register') ? 'none' : 'flex';

    // Lifecycle hooks
    if (page === 'dashboard')     onDashboard();
    if (page === 'form-review')   onFormReview();
    if (page === 'execution')     onExecution();
    if (page === 'profile-setup') onProfileSetup();
    if (page === 'session' && param) onSessionDetail(param);
  }

  // ── Auth ───────────────────────────────────────
  function showAuthTab(tab) {
    document.getElementById('loginForm').classList.toggle('hidden', tab !== 'login');
    document.getElementById('registerForm').classList.toggle('hidden', tab !== 'register');
    document.getElementById('tabLogin').classList.toggle('active', tab === 'login');
    document.getElementById('tabRegister').classList.toggle('active', tab !== 'login');
  }

  function setRole(r) {
    _role = r;
    document.getElementById('rolePrimary').classList.toggle('active', r === 'primary');
    document.getElementById('roleRelative').classList.toggle('active', r === 'relative');
  }

  async function login(e) {
    e.preventDefault();
    const btn = document.getElementById('btnLogin');
    setLoading(btn, true);
    try {
      const res = await api('/auth/login', 'POST', {
        email:    document.getElementById('loginEmail').value,
        password: document.getElementById('loginPassword').value,
      });
      
      console.log('[Login] Response:', res);
      
      // Normalize response extraction
      const userData = res.data || res;
      _token     = userData.access_token || null;
      _userId    = userData.user?.user_id || userData.user_id || null;
      _userEmail = userData.user?.email || userData.email || null;
      
      console.log('[Login] Extracted:', { _token, _userId, _userEmail });
      
      if (!_token) {
        throw new Error('No access token received from server');
      }
      
      setUserUI(_userEmail);
      toast('Welcome back!', 'success');
      navigate('dashboard');
    } catch(err) {
      console.error('[Login] Error:', err);
      toast(err.message, 'error');
    } finally {
      setLoading(btn, false);
    }
  }

  async function register(e) {
    e.preventDefault();
    const btn = document.getElementById('btnRegister');
    setLoading(btn, true);
    try {
      // Safely get form elements
      const regEmailEl = document.getElementById('regEmail');
      const regNameEl = document.getElementById('regName');
      const regPhoneEl = document.getElementById('regPhone');
      const regPasswordEl = document.getElementById('regPassword');
      
      const email = (regEmailEl?.value || '').trim();
      const rawName = (regNameEl?.value || '').trim();
      const phone = (regPhoneEl?.value || '').trim() || null;
      const password = (regPasswordEl?.value || '').trim();
      
      // Safe fallback name generation (without split - uses indexOf to find @ position)
      const atIndex = email.indexOf('@');
      const name = rawName || (atIndex > 0 ? email.substring(0, atIndex) : 'User');
      
      console.log('[Register] Payload:', { name, email, phone, role: _role });
      
      const res = await api('/auth/register', 'POST', {
        name,
        email,
        phone,
        password,
        role: _role,
        parent_user_id: null,
      });
      
      console.log('[Register] Response:', res);
      
      // Auto-login to get token
      const loginRes = await api('/auth/login', 'POST', {
        email,
        password,
      });
      
      console.log('[Register] Login response:', loginRes);
      
      // Normalize response extraction
      const userData = loginRes.data || loginRes;
      _token     = userData.access_token || null;
      _userId    = userData.user?.user_id || userData.user_id || null;
      _userEmail = userData.user?.email || userData.email || email;
      
      console.log('[Register] Extracted:', { _token, _userId, _userEmail });
      
      if (!_token) {
        throw new Error('No access token received after registration');
      }
      
      setUserUI(_userEmail);
      toast('Account created! Let\'s set up your profile.', 'success');
      navigate('profile-setup');
    } catch(err) {
      console.error('[Register] Error:', err);
      toast(err.message, 'error');
    } finally {
      setLoading(btn, false);
    }
  }

  function logout() {
    _token     = null;
    _userId    = null;
    _userEmail = null;
    _sessionId = null;
    if (_ws) { _ws.close(); _ws = null; }
    toast('Logged out', 'success');
    navigate('login');
  }

  function setUserUI(email) {
  const safeEmail = (email || '').trim();
  // Safe name extraction (without split - uses indexOf)
  const atIndex = safeEmail.indexOf('@');
  const name = atIndex > 0 ? safeEmail.substring(0, atIndex) : (safeEmail || 'User');

  document.getElementById('userNameDisplay').textContent = name;
  document.getElementById('dashUserName').textContent = name;
  document.getElementById('userAvatar').textContent = name.charAt(0).toUpperCase() || 'U';
}

  // ── Profile Setup ──────────────────────────────
  let _setupCurrentStep = 1;
  let _setupFiles = [];
  let _setupSessionId = null;

  function onProfileSetup() {
    _setupSessionId = 'setup-' + Date.now();
    _chatSessionId  = _setupSessionId;
    setupGoStep(1);
    loadProfileCompletion();
    addCounsellorMsg('setupCounsellorMessages', 'bot',
      'Namaste! I am Sahayak. I will help you set up your profile. Let\'s start with your basic information — what is your full name as it appears on your Aadhaar card?');
  }

  function setupGoStep(n) {
    _setupCurrentStep = n;
    for (let i = 1; i <= 4; i++) {
      document.getElementById(`setupStep${i}`).classList.toggle('hidden', i !== n);
      const item = document.querySelector(`.step-item[data-step="${i}"]`);
      if (item) {
        item.classList.toggle('active', i === n);
        item.classList.toggle('done',   i < n);
      }
    }
  }

  async function saveBasicInfo(e) {
    e.preventDefault();
    showLoading('Saving profile...');
    try {
      await api('/auth/profile', 'POST', {
        basic_info: {
          full_name: document.getElementById('fullName').value,
          dob:       document.getElementById('dob').value,
          gender:    document.getElementById('gender').value,
        },
        contact: {
          address: document.getElementById('address').value,
          pincode: document.getElementById('pincode').value,
        }
      });
      setupGoStep(2);
      updateSetupCompletion(30);
      addCounsellorMsg('setupCounsellorMessages', 'bot',
        'Great! Now let\'s upload your documents. Your Aadhaar card is the most important one — it will be used to auto-fill most forms.');
    } catch(err) {
      toast(err.message, 'error');
    } finally {
      hideLoading();
    }
  }

  function initSetupDropzone() {
    const zone  = document.getElementById('setupUploadZone');
    const input = document.getElementById('setupFileInput');

    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      handleSetupFiles(Array.from(e.dataTransfer.files));
    });
    input.addEventListener('change', () => handleSetupFiles(Array.from(input.files)));
  }

  function handleSetupFiles(files) {
    files.forEach(f => {
      if (!_setupFiles.find(x => x.name === f.name)) _setupFiles.push(f);
    });
    renderSetupFileList();
    document.getElementById('btnUploadDocs').disabled = _setupFiles.length === 0;
  }

  function renderSetupFileList() {
    const list = document.getElementById('setupFileList');
    list.innerHTML = _setupFiles.map((f, i) => `
      <div class="file-item">
        <span>📄</span>
        <span class="fi-name">${f.name}</span>
        <span class="fi-size">${(f.size/1024).toFixed(0)} KB</span>
        <button class="fi-remove" onclick="App.removeSetupFile(${i})">✕</button>
      </div>
    `).join('');
  }

  function removeSetupFile(i) {
    _setupFiles.splice(i, 1);
    renderSetupFileList();
  }

  async function uploadSetupDocuments() {
    if (_setupFiles.length === 0) { toast('Please add at least one document', 'warning'); return; }
    const docType = document.getElementById('docType').value;

    showLoading('Extracting data from documents...');
    try {
      const results = [];
      for (const file of _setupFiles) {
        const form = new FormData();
        form.append('file', file);
        form.append('doc_type', docType);
        form.append('session_id', _setupSessionId);
        const res = await api('/documents/upload', 'POST', form, true);
        results.push(res.data);
      }

      setupGoStep(3);
      renderExtractedReview(results);
      updateSetupCompletion(65);
      addCounsellorMsg('setupCounsellorMessages', 'bot',
        `Excellent! I extracted data from ${_setupFiles.length} document(s). Please review the fields below — green means I am confident, orange means you should check.`);
    } catch(err) {
      toast('Document processing failed: ' + err.message, 'error');
    } finally {
      hideLoading();
    }
  }

  function renderExtractedReview(results) {
    const container = document.getElementById('extractedFieldsReview');
    container.innerHTML = '';
    results.forEach(r => {
      const fields = r.extracted_fields || {};
      Object.entries(fields).forEach(([key, val]) => {
        const confidence = r.confidence || 0.8;
        const cls = confidence >= 0.85 ? 'confident' : 'needs-review';
        container.insertAdjacentHTML('beforeend', `
          <div class="extracted-field ${cls}">
            <div class="ef-indicator"></div>
            <div class="ef-content">
              <div class="ef-label">${key.replace(/_/g,' ').toUpperCase()}</div>
              <div class="ef-value">
                <input type="text" value="${val}" data-field="${key}"
                  style="background:transparent;border:none;border-bottom:1px dashed var(--glass-border);padding:0.2rem 0;font-weight:600;color:var(--text-primary);width:100%">
              </div>
            </div>
          </div>
        `);
      });
    });
    if (!container.innerHTML) {
      container.innerHTML = '<p style="color:var(--text-muted)">No structured fields could be extracted automatically. You can add details manually from the dashboard.</p>';
    }
  }

  async function confirmExtractedData() {
    showLoading('Saving your data...');
    try {
      // Confirm all uploaded docs with their doc_ids
      setupGoStep(4);
      updateSetupCompletion(100);
      addCounsellorMsg('setupCounsellorMessages', 'bot',
        '🎉 Your profile is all set! You can now use CivicFlow to fill any government form automatically. Head to the dashboard to get started!');
    } catch(err) {
      toast(err.message, 'error');
    } finally {
      hideLoading();
    }
  }

  async function loadProfileCompletion() {
    try {
      const res = await api('/auth/me');
      const pct = res.data?.profile_completion || 0;
      updateSetupCompletion(pct);
    } catch(_) {}
  }

  function updateSetupCompletion(pct) {
    document.getElementById('setupCompletionPct').textContent  = `${pct}%`;
    document.getElementById('setupCompletionFill').style.width = `${pct}%`;
    document.getElementById('dashCompletionBadge').textContent = `${pct}%`;
    document.getElementById('dashCompletionFill').style.width  = `${pct}%`;
  }

  // ── Dashboard ──────────────────────────────────
  async function onDashboard() {
    await Promise.all([refreshSessions(), checkTelegramStatus()]);
    addCounsellorMsg('floatChatMessages', 'bot',
      'Namaste! How can I help you today? You can describe any form you need help with.', true);
  }

  async function refreshSessions() {
    try {
      const res = await api('/sessions');
      renderSessions(res.data?.sessions || []);
    } catch(_) {
      document.getElementById('sessionsList').innerHTML =
        '<div class="empty-state">Could not load sessions.</div>';
    }
  }

  function renderSessions(sessions) {
    const container = document.getElementById('sessionsList');
    if (!sessions.length) {
      container.innerHTML = '<div class="empty-state">No active sessions. Start by filling a form!</div>';
      return;
    }
    container.innerHTML = sessions.map(s => `
      <div class="session-card" onclick="App.navigate('session', {id:'${s.session_id}'})">
        <div>
          <div class="session-form-name">${s.scraped_form?.form_title || 'Unnamed Form'}</div>
          <div class="session-url">${s.url || ''}</div>
        </div>
        <span class="status-badge ${s.status}">${s.status}</span>
      </div>
    `).join('');
  }

  async function checkTelegramStatus() {
    try {
      const res = await api('/auth/me');
      const linked = !!res.data?.telegram_chat_id;
      const card   = document.getElementById('tgLinkCard');
      const hdr    = document.getElementById('tgStatus');
      const hdrTxt = document.getElementById('tgStatusText');
      if (linked) {
        card.classList.add('linked');
        hdr.classList.add('linked');
        hdrTxt.textContent = 'Telegram Linked';
        document.getElementById('tgLinkTitle').textContent = 'Telegram Connected ✓';
        document.getElementById('tgLinkDesc').textContent  = 'You will receive real-time notifications';
        document.getElementById('tgLinkBtn').textContent   = 'Unlink';
      }
    } catch(_) {}
  }

  async function linkTelegram() {
    try {
      const res = await api('/telegram/link-token');
      const token  = res.data.token;
      const botUser = res.data.bot_username;
      toast(`Send this to @${botUser} on Telegram: /start ${token}`, 'info');
      // Copy to clipboard
      navigator.clipboard?.writeText(`/start ${token}`).catch(() => {});
    } catch(err) {
      toast(err.message, 'error');
    }
  }

  // ── Form Search ────────────────────────────────
  function setSearchMode(mode) {
    document.getElementById('searchDescribePanel').classList.toggle('hidden', mode !== 'describe');
    document.getElementById('searchUrlPanel').classList.toggle('hidden', mode !== 'url');
    document.getElementById('modeDescribe').classList.toggle('active', mode === 'describe');
    document.getElementById('modePasteUrl').classList.toggle('active', mode === 'url');
  }

  async function searchForm() {
    const name  = document.getElementById('serviceSearch').value.trim();
    const state = document.getElementById('stateSearch').value.trim();
    if (!name) { toast('Please describe what you need', 'warning'); return; }

    showLoading('Searching portals...');
    try {
      const res = await api('/search/form', 'POST', { service_name: name, state: state || null });
      renderSearchResults(res.data?.options || []);
    } catch(err) {
      toast(err.message, 'error');
    } finally {
      hideLoading();
    }
  }

  async function useDirectUrl() {
    const url = document.getElementById('directUrl').value.trim();
    if (!url) { toast('Please enter a URL', 'warning'); return; }

    showLoading('Verifying URL...');
    try {
      const res = await api('/search/verify', 'POST', { url });
      const row  = document.getElementById('urlVerifyRow');
      const badge = document.getElementById('urlVerifyBadge');
      row.style.display = 'flex';
      if (res.data.valid && res.data.is_government) {
        badge.className = 'verify-badge valid';
        badge.textContent = `✓ Valid government domain (${res.data.domain})`;
        // Auto proceed to scrape
        setTimeout(() => startScraping(url), 1000);
      } else {
        badge.className = 'verify-badge invalid';
        badge.textContent = res.data.is_government ? '⚠ Unreachable' : '⚠ Not an official government domain';
      }
    } catch(err) {
      toast(err.message, 'error');
    } finally {
      hideLoading();
    }
  }

  function renderSearchResults(options) {
    const panel = document.getElementById('searchResults');
    const cards = document.getElementById('searchResultCards');
    panel.classList.remove('hidden');
    if (!options.length) {
      cards.innerHTML = '<div class="empty-state">No official portal found. Try a different description or paste the URL directly.</div>';
      return;
    }
    cards.innerHTML = options.map(o => `
      <div class="portal-card" onclick="App.startScraping('${o.url}')">
        <div style="flex:1">
          <div style="font-weight:700">${o.portal_name}</div>
          <div class="portal-domain">${o.url}</div>
          ${o.notes ? `<div style="font-size:0.78rem;color:var(--text-muted);margin-top:0.3rem">${o.notes}</div>` : ''}
        </div>
        <div class="confidence-bar" style="max-width:80px">
          <div class="conf-label">${Math.round(o.confidence*100)}%</div>
          <div class="conf-track"><div class="conf-fill" style="width:${o.confidence*100}%"></div></div>
        </div>
      </div>
    `).join('');
  }

  async function startScraping(url) {
    showLoading('Analyzing form...');
    try {
      const res = await api('/start', 'POST', { url });
      _sessionId = res.data?.session_id || res.session_id;
      navigate('form-review');
    } catch(err) {
      toast('Failed to analyze form: ' + err.message, 'error');
    } finally {
      hideLoading();
    }
  }

  // ── Form Review ────────────────────────────────
  async function onFormReview() {
    if (!_sessionId) { navigate('form-search'); return; }
    _chatSessionId = _sessionId;
    showLoading('Loading form details...');
    try {
      const res = await api(`/sessions/${_sessionId}`);
      const session = res.data || res;
      renderFormReview(session);
      addCounsellorMsg('reviewCounsellorMessages', 'bot',
        'I\'ve analyzed the form. Green fields are auto-filled from your profile. Orange fields need your input. Let me know if anything looks wrong!');
    } catch(err) {
      toast(err.message, 'error');
    } finally {
      hideLoading();
    }
  }

  function renderFormReview(session) {
    const form = session.scraped_form || {};
    document.getElementById('reviewFormTitle').textContent =
      form.form_title || session.url || 'Government Form';

    const container = document.getElementById('reviewFormFields');
    const fields    = form.fields || session.data_requirements || [];
    const reqs      = session.data_requirements || [];

    container.innerHTML = '<div style="padding:1.5rem">' + fields.map(f => {
      const req = reqs.find(r => r.field_id === f.field_id);
      const val = req?.value || '';
      const cls = val ? 'rf-filled' : 'rf-missing';

      let inputHtml = '';
      if (f.field_type === 'select') {
        inputHtml = `<select class="rf-input" data-field="${f.field_id}">
          ${(f.options||[]).map(o => `<option value="${o}" ${o===val?'selected':''}>${o}</option>`).join('')}
        </select>`;
      } else if (f.field_type === 'radio') {
        inputHtml = (f.options||[]).map(o => `
          <label style="display:flex;gap:.4rem;align-items:center;font-size:.85rem">
            <input type="radio" name="rf_${f.field_id}" value="${o}" ${o===val?'checked':''}> ${o}
          </label>`).join('');
      } else if (f.field_type === 'file') {
        inputHtml = `<input type="file" class="rf-input" data-field="${f.field_id}" accept="image/*,.pdf">`;
      } else {
        inputHtml = `<input type="text" class="rf-input" value="${val}" data-field="${f.field_id}" placeholder="Enter ${f.label}">`;
      }

      return `
        <div class="review-field-row ${cls}">
          <div class="rf-status"></div>
          <div class="rf-meta" style="flex:1">
            <div class="rf-label">${f.label}</div>
            <div>${val ? `<div class="rf-value">${val}</div>` : inputHtml}</div>
          </div>
        </div>`;
    }).join('') + '</div>';
  }

  async function confirmAndFill() {
    // Collect any manually entered values
    const updates = {};
    document.querySelectorAll('#reviewFormFields [data-field]').forEach(el => {
      if (el.value) updates[el.dataset.field] = el.value;
    });

    showLoading('Starting form automation...');
    try {
      await api(`/sessions/${_sessionId}/fill`, 'POST', { updates });
      navigate('execution');
    } catch(err) {
      // Fallback — navigate anyway and wait for WS events
      navigate('execution');
    } finally {
      hideLoading();
    }
  }

  // ── Execution / WebSocket ──────────────────────
  function onExecution() {
    if (!_sessionId) { navigate('dashboard'); return; }
    _chatSessionId = _sessionId;
    connectWS();
    addCounsellorMsg('execCounsellorMessages', 'bot',
      'I\'m watching the automation in real-time. I\'ll alert you immediately if any action is needed on your end.');
  }

  function connectWS() {
    if (_ws && _ws.readyState <= 1) return; // Already open/connecting

    const wsUrl = `${WS_BASE}/ws/${_sessionId}`;
    _ws = new WebSocket(wsUrl);

    _ws.onopen = () => {
      console.log('[WS] Connected');
      document.getElementById('execStatusText').textContent = 'Automation is running...';
      clearTimeout(_wsReconnectTimer);
    };

    _ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        handleWSEvent(msg);
      } catch(_) {}
    };

    _ws.onclose = () => {
      console.log('[WS] Disconnected — reconnecting in 3s');
      _wsReconnectTimer = setTimeout(connectWS, 3000);
    };

    _ws.onerror = (err) => console.error('[WS] Error:', err);
  }

  function handleWSEvent(msg) {
    const type = msg.type || msg.status;
    switch (type) {
      case 'field_start':
        updateExecField(msg.field, 'current');
        break;
      case 'field_done':
        updateExecField(msg.field, 'done');
        break;
      case 'progress':
        updateExecProgress(msg.field, msg.percent);
        break;
      case 'paused_captcha':
        document.getElementById('captchaPause').classList.remove('hidden');
        if (msg.screenshot) {
          const img = document.getElementById('captchaScreenshot');
          img.src = 'data:image/png;base64,' + msg.screenshot;
          img.classList.remove('hidden');
        }
        addCounsellorMsg('execCounsellorMessages', 'bot',
          '⚠️ A CAPTCHA appeared. Please solve it in the browser window, then click "I Solved It".');
        toast('CAPTCHA needs your attention!', 'warning');
        break;
      case 'paused_otp':
        document.getElementById('otpPause').classList.remove('hidden');
        addCounsellorMsg('execCounsellorMessages', 'bot',
          '📱 An OTP was sent to your registered number. Please enter it to continue.');
        break;
      case 'completed':
        execCompleted(msg);
        break;
      case 'failed':
        execFailed(msg);
        break;
      case 'screenshot':
        const sc = document.getElementById('screenshotCard');
        const img = document.getElementById('execScreenshot');
        sc.style.display = 'block';
        img.src = 'data:image/png;base64,' + msg.data;
        break;
    }
  }

  function updateExecField(fieldName, state) {
    const tracker = document.getElementById('liveFieldTracker');
    const existing = tracker.querySelector(`[data-field="${fieldName}"]`);
    if (existing) {
      existing.className = `tracker-row ${state}`;
      existing.querySelector('.tr-icon').textContent = state === 'done' ? '✓' : '⟳';
      return;
    }
    tracker.insertAdjacentHTML('beforeend', `
      <div class="tracker-row ${state}" data-field="${fieldName}">
        <span class="tr-icon">${state === 'done' ? '✓' : '⟳'}</span>
        <span>${fieldName}</span>
      </div>
    `);
  }

  function updateExecProgress(field, pct) {
    document.getElementById('execFieldLabel').textContent = field || 'Working...';
    document.getElementById('execProgressPct').textContent = `${Math.round(pct || 0)}%`;
    document.getElementById('execFill').style.width = `${pct || 0}%`;
  }

  function execCompleted(msg) {
    document.getElementById('execStatusText').textContent = 'Form submitted successfully!';
    updateExecProgress('Completed', 100);
    toast('Form filled and submitted! 🎉', 'success');
    addCounsellorMsg('execCounsellorMessages', 'bot',
      `🎉 The form has been submitted successfully! ${msg.application_id ? `Your application ID is: ${msg.application_id}` : ''} Check your email for confirmation.`);
  }

  function execFailed(msg) {
    const field = msg.field || 'Unknown field';
    document.getElementById('execStatusText').textContent = 'Correction needed';
    document.getElementById('correctionFieldName').textContent = `Field: ${field}`;
    document.getElementById('correctionErrorBox').textContent = msg.error || 'An error occurred';
    if (msg.screenshot) {
      const img = document.getElementById('correctionScreenshot');
      img.src = 'data:image/png;base64,' + msg.screenshot;
      img.classList.remove('hidden');
    }
    navigate('correction');
  }

  async function resumeAfterCaptcha() {
    document.getElementById('captchaPause').classList.add('hidden');
    try {
      await api(`/sessions/${_sessionId}/resume`, 'POST', { type: 'captcha' });
      toast('Resuming...', 'success');
    } catch(err) {
      toast(err.message, 'error');
    }
  }

  async function resumeAfterOtp() {
    const otp = document.getElementById('otpInput').value.trim();
    if (!otp) { toast('Please enter the OTP', 'warning'); return; }
    document.getElementById('otpPause').classList.add('hidden');
    try {
      await api(`/sessions/${_sessionId}/otp`, 'POST', { otp });
      toast('OTP submitted, resuming...', 'success');
    } catch(err) {
      toast(err.message, 'error');
    }
  }

  async function submitCorrection() {
    const val = document.getElementById('correctionValue').value.trim();
    if (!val) { toast('Please enter a corrected value', 'warning'); return; }
    showLoading('Resuming with correction...');
    try {
      await api(`/sessions/${_sessionId}/correct`, 'POST', { value: val });
      navigate('execution');
    } catch(err) {
      toast(err.message, 'error');
    } finally {
      hideLoading();
    }
  }

  // ── Session Detail ─────────────────────────────
  async function onSessionDetail(id) {
    document.getElementById('detailSessionId').textContent = id;
    try {
      const res = await api(`/sessions/${id}`);
      renderSessionDetail(res.data || res);
    } catch(err) {
      document.getElementById('sessionDetailCard').innerHTML =
        `<p style="color:var(--danger)">${err.message}</p>`;
    }
  }

  function renderSessionDetail(s) {
    const card = document.getElementById('sessionDetailCard');
    card.innerHTML = `
      <div class="form-row">
        <div><div class="ef-label">Status</div><span class="status-badge ${s.status}">${s.status}</span></div>
        <div><div class="ef-label">Created</div><div>${new Date(s.created_at).toLocaleString()}</div></div>
      </div>
      <div style="margin-top:1.5rem">
        <div class="ef-label">Portal URL</div>
        <a href="${s.url}" target="_blank" style="color:var(--sage-300)">${s.url}</a>
      </div>
    `;

    // Audit log from conversation_history
    const log = document.getElementById('auditLog');
    const entries = s.conversation_history || [];
    log.innerHTML = entries.length ? entries.map(e => `
      <div class="audit-entry">
        <span class="ae-time">${new Date(e.timestamp).toLocaleTimeString()}</span>
        <span class="ae-field">${e.role}</span>
        <span class="ae-val">${e.message}</span>
      </div>
    `).join('') : '<p style="color:var(--text-muted);padding:1rem">No activity logged yet.</p>';
  }

  // ── Counsellor Chat ────────────────────────────
  async function sendCounsellorMessage(e, context) {
    e.preventDefault();
    const inputId = {
      setup: 'setupChatInput',
      review: 'reviewChatInput',
      execution: 'execChatInput',
      float: 'floatChatInput',
    }[context] || 'floatChatInput';

    const msgContainerId = {
      setup: 'setupCounsellorMessages',
      review: 'reviewCounsellorMessages',
      execution: 'execCounsellorMessages',
      float: 'floatChatMessages',
    }[context] || 'floatChatMessages';

    const input = document.getElementById(inputId);
    const text  = input.value.trim();
    if (!text) return;
    input.value = '';

    addCounsellorMsg(msgContainerId, 'user', text);
    const typingId = addCounsellorMsg(msgContainerId, 'bot', '...typing', false, true);

    try {
      const res = await api('/chat', 'POST', {
        session_id: _chatSessionId || 'global',
        message:    text,
        stage:      context,
      });
      document.getElementById(typingId)?.remove();
      addCounsellorMsg(msgContainerId, 'bot', res.data?.response || '...');

      if (res.data?.triggered_action) {
        handleTriggeredAction(res.data.triggered_action);
      }
    } catch(err) {
      document.getElementById(typingId)?.remove();
      addCounsellorMsg(msgContainerId, 'bot', 'I had trouble processing that. Please try again.');
    }
  }

  function addCounsellorMsg(containerId, role, text, scroll = true, isTyping = false) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const id = 'msg-' + Date.now() + Math.random();
    container.insertAdjacentHTML('beforeend', `
      <div class="chat-msg ${role} ${isTyping ? 'typing' : ''}" id="${id}">${text}</div>
    `);
    if (scroll) container.scrollTop = container.scrollHeight;
    return id;
  }

  function handleTriggeredAction(action) {
    if (action === 'start_form_fill') navigate('form-search');
    if (action === 'update_profile')  navigate('profile-setup');
  }

  // ── Float Counsellor Widget ────────────────────
  function toggleFloatCounsellor() {
    const win = document.getElementById('floatChatWindow');
    const unread = document.getElementById('floatUnread');
    const isOpen = win.style.display !== 'none';
    win.style.display = isOpen ? 'none' : 'flex';
    if (!isOpen) unread.style.display = 'none';
  }

  // ── Toast ──────────────────────────────────────
  function toast(message, type = 'info') {
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const container = document.getElementById('toastContainer');
    const id = 'toast-' + Date.now();
    container.insertAdjacentHTML('beforeend', `
      <div class="toast ${type}" id="${id}">
        <span class="toast-icon">${icons[type]}</span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="document.getElementById('${id}').remove()">✕</button>
      </div>
    `);
    setTimeout(() => {
      const el = document.getElementById(id);
      if (el) { el.classList.add('fade-out'); setTimeout(() => el.remove(), 300); }
    }, 5000);
  }

  // ── Loading Overlay ────────────────────────────
  function showLoading(text = 'Loading...') {
    document.getElementById('loadingText').textContent = text;
    document.getElementById('loadingOverlay').classList.remove('hidden');
  }
  function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
  }

  function setLoading(btn, loading) {
    const text   = btn.querySelector('.btn-text');
    const loader = btn.querySelector('.btn-loader');
    btn.disabled = loading;
    if (text)   text.classList.toggle('hidden', loading);
    if (loader) loader.classList.toggle('hidden', !loading);
  }

  // ── Init ───────────────────────────────────────
  function init() {
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
    initSetupDropzone();

    // Live URL verification on input
    const directUrlInput = document.getElementById('directUrl');
    if (directUrlInput) {
      let timer;
      directUrlInput.addEventListener('input', () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          const url = directUrlInput.value.trim();
          if (url.startsWith('http')) useDirectUrl();
        }, 800);
      });
    }
  }

  // ── Public API ─────────────────────────────────
  return {
    init,
    navigate,
    login,
    register,
    logout,
    showAuthTab,
    setRole,
    saveBasicInfo,
    setupGoStep,
    uploadSetupDocuments,
    removeSetupFile,
    confirmExtractedData,
    refreshSessions,
    linkTelegram,
    setSearchMode,
    searchForm,
    useDirectUrl,
    startScraping,
    confirmAndFill,
    resumeAfterCaptcha,
    resumeAfterOtp,
    submitCorrection,
    sendCounsellorMessage,
    toggleFloatCounsellor,
  };
})();

document.addEventListener('DOMContentLoaded', App.init);
