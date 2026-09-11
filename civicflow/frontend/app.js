const API_BASE = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000';

const state = {
    sessionId: null,
    currentView: 'start',
    dataRequirements: [],
    uploadedFiles: [],
    documentFields: [],
    textFields: [],
    ws: null,
    statusPollInterval: null
};

// View Management
function showView(viewName) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${viewName}`).classList.add('active');
    state.currentView = viewName;
}

function showError(message) {
    const banner = document.getElementById('errorBanner');
    const messageEl = document.getElementById('errorMessage');
    messageEl.textContent = message;
    banner.style.display = 'flex';
}

function hideError() {
    document.getElementById('errorBanner').style.display = 'none';
}

function showLoading(text = 'Processing...') {
    document.getElementById('loadingOverlay').style.display = 'flex';
    document.getElementById('loadingText').textContent = text;
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

// VIEW 1: Start Session
async function startSession() {
    const url = document.getElementById('formUrl').value.trim();
    if (!url) {
        showError('Please enter a form URL');
        return;
    }

    hideError();
    showLoading('Analyzing form...');

    try {
        const response = await fetch(`${API_BASE}/sessions/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create session');
        }

        const data = await response.json();
        state.sessionId = data.session_id;
        
        document.getElementById('sessionId').textContent = data.session_id.substring(0, 8) + '...';
        document.getElementById('sessionInfo').style.display = 'flex';

        showView('documents');
    } catch (error) {
        showError(error.message);
    } finally {
        hideLoading();
    }
}

// VIEW 2: Document Upload
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

function handleFiles(files) {
    state.uploadedFiles = [...state.uploadedFiles, ...Array.from(files)];
    renderFileList();
    document.getElementById('btnProcessDocs').style.display = state.uploadedFiles.length > 0 ? 'flex' : 'none';
}

function renderFileList() {
    fileList.innerHTML = state.uploadedFiles.map(file => `
        <div class="file-item">
            <span class="file-icon">📄</span>
            <span class="file-name">${file.name}</span>
            <span class="file-size">${(file.size / 1024).toFixed(1)} KB</span>
            <span class="file-check">✓</span>
        </div>
    `).join('');
}

async function processDocuments() {
    hideError();
    showLoading('Processing documents...');

    try {
        // Upload documents
        const formData = new FormData();
        state.uploadedFiles.forEach(file => formData.append('files', file));

        const uploadResponse = await fetch(`${API_BASE}/sessions/${state.sessionId}/documents`, {
            method: 'POST',
            body: formData
        });

        if (!uploadResponse.ok) {
            const error = await uploadResponse.json();
            throw new Error(error.detail || 'Failed to upload documents');
        }

        showLoading('Analyzing form fields...');

        // Run analysis
        const runResponse = await fetch(`${API_BASE}/sessions/${state.sessionId}/run`, {
            method: 'POST'
        });

        if (!runResponse.ok) {
            const error = await runResponse.json();
            throw new Error(error.detail || 'Failed to analyze form');
        }

        // Wait for analysis to complete and fetch data requirements
        await waitForAnalysisComplete();
        
    } catch (error) {
        showError(error.message);
        hideLoading();
    }
}

// Skip document upload — run analysis directly with no docs
async function skipDocuments() {
    hideError();
    showLoading('Analyzing form fields...');

    try {
        const runResponse = await fetch(`${API_BASE}/sessions/${state.sessionId}/run`, {
            method: 'POST'
        });

        if (!runResponse.ok) {
            const error = await runResponse.json();
            throw new Error(error.detail || 'Failed to analyze form');
        }

        await waitForAnalysisComplete();

    } catch (error) {
        showError(error.message);
        hideLoading();
    }
}

async function waitForAnalysisComplete() {
    const maxAttempts = 20;
    let attempts = 0;

    while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        try {
            const response = await fetch(`${API_BASE}/sessions/${state.sessionId}/status`);
            const data = await response.json();

            // Accept 'collecting' (needs user input) OR 'ready' (all pre-filled from docs)
            const isAnalysisDone = (
                (data.status === 'collecting' || data.status === 'ready') &&
                data.data_requirements &&
                data.data_requirements.length > 0
            );

            if (isAnalysisDone) {
                state.dataRequirements = data.data_requirements;
                hideLoading();
                renderDataCollection();
                showView('collect');
                return;
            } else if (data.status === 'failed') {
                throw new Error(data.error || 'Analysis failed');
            }
        } catch (error) {
            if (attempts === maxAttempts - 1) {
                throw error;
            }
        }
        
        attempts++;
    }

    throw new Error('Analysis timeout - please try again');
}

// VIEW 3: Data Collection with Document Upload
function renderDataCollection() {
    // Separate document fields from text fields
    state.documentFields = state.dataRequirements.filter(item => item.input_type === 'document');
    state.textFields = state.dataRequirements.filter(item => item.input_type !== 'document');

    const dataForm = document.getElementById('dataForm');
    let html = '';

    // Render document upload section
    if (state.documentFields.length > 0) {
        html += '<div class="document-section"><h3 class="section-title">📎 Documents Required</h3>';
        
        state.documentFields.forEach(field => {
            const isUploaded = field.document_path !== null;
            html += `
                <div class="document-field" data-field-id="${field.field_id}">
                    <div class="document-header">
                        <span class="document-name">${field.label}</span>
                        ${isUploaded ? '<span class="upload-badge success">✓ Uploaded</span>' : '<span class="upload-badge pending">Required</span>'}
                    </div>
                    <p class="document-description">${field.description}</p>
                    <div class="document-meta">${field.example}</div>
                    ${!isUploaded ? `
                        <div class="upload-button-wrapper">
                            <input type="file" id="doc-${field.field_id}" class="document-input" accept=".pdf,.jpg,.jpeg,.png" data-field-id="${field.field_id}">
                            <button type="button" class="btn btn-secondary" onclick="document.getElementById('doc-${field.field_id}').click()">
                                <span class="btn-text">Choose File</span>
                                <span class="btn-icon">📁</span>
                            </button>
                            <span class="upload-filename" id="filename-${field.field_id}"></span>
                        </div>
                        <div class="field-error" id="error-${field.field_id}" style="display: none;"></div>
                    ` : `
                        <div class="uploaded-file">
                            <span class="uploaded-icon">✓</span>
                            <span>${field.document_path ? field.document_path.split('/').pop() : 'Document uploaded'}</span>
                        </div>
                    `}
                </div>
            `;
        });
        
        html += '</div>';
    }

    // Render text fields section
    if (state.textFields.length > 0) {
        html += '<div class="text-fields-section"><h3 class="section-title">📝 Your Information</h3>';
        
        state.textFields.forEach(field => {
            const isAutoFilled = field.extracted_from_doc;
            html += `
                <div class="form-field ${isAutoFilled ? 'auto-filled' : ''}">
                    <label class="field-label">
                        ${field.label}
                        ${isAutoFilled ? '<span class="auto-badge">✓ Auto-filled</span>' : ''}
                    </label>
                    ${field.description ? `<p class="field-description">${field.description}</p>` : ''}
                    <input 
                        type="${field.input_type === 'date' ? 'date' : 'text'}" 
                        id="field-${field.field_id}"
                        class="field-input"
                        placeholder="${field.example}"
                        value="${field.value || ''}"
                        ${isAutoFilled ? 'readonly' : ''}
                    />
                    ${isAutoFilled ? `<button type="button" class="edit-btn" onclick="enableEdit('${field.field_id}')">Edit</button>` : ''}
                </div>
            `;
        });
        
        html += '</div>';
    }

    dataForm.innerHTML = html;

    // Update description
    const autoFilled = state.textFields.filter(f => f.extracted_from_doc).length;
    const total = state.textFields.length;
    document.getElementById('collectDescription').textContent = 
        `${autoFilled} of ${total} fields were auto-filled from your documents. Please review and complete any missing information.`;

    // Attach document upload listeners
    state.documentFields.forEach(field => {
        const input = document.getElementById(`doc-${field.field_id}`);
        if (input) {
            input.addEventListener('change', (e) => handleDocumentUpload(field.field_id, e.target.files[0]));
        }
    });
}

async function handleDocumentUpload(fieldId, file) {
    if (!file) return;

    const filenameEl = document.getElementById(`filename-${fieldId}`);
    const errorEl = document.getElementById(`error-${fieldId}`);
    
    filenameEl.textContent = 'Uploading...';
    errorEl.style.display = 'none';

    try {
        const formData = new FormData();
        formData.append('files', file);

        const response = await fetch(`${API_BASE}/sessions/${state.sessionId}/documents`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Upload failed');
        }

        // Update state
        const field = state.documentFields.find(f => f.field_id === fieldId);
        if (field) {
            field.document_path = file.name;
        }

        // Re-render to show success
        renderDataCollection();

    } catch (error) {
        errorEl.textContent = `Upload failed: ${error.message}`;
        errorEl.style.display = 'block';
        filenameEl.textContent = '';
    }
}

function enableEdit(fieldId) {
    const input = document.getElementById(`field-${fieldId}`);
    input.removeAttribute('readonly');
    input.focus();
    input.classList.remove('readonly');
}

async function startFormFilling() {
    hideError();

    // Validate all documents are uploaded
    const missingDocs = state.documentFields.filter(f => !f.document_path);
    if (missingDocs.length > 0) {
        missingDocs.forEach(doc => {
            const errorEl = document.getElementById(`error-${doc.field_id}`);
            if (errorEl) {
                errorEl.textContent = `Please upload your ${doc.label} before proceeding`;
                errorEl.style.display = 'block';
            }
        });
        showError(`Please upload all required documents before proceeding`);
        return;
    }

    // Collect all field values
    const fields = [];
    
    state.textFields.forEach(field => {
        const input = document.getElementById(`field-${field.field_id}`);
        fields.push({
            field_id: field.field_id,
            value: input ? input.value : field.value
        });
    });

    state.documentFields.forEach(field => {
        fields.push({
            field_id: field.field_id,
            value: field.document_path
        });
    });

    showLoading('Preparing automation...');

    try {
        // Fill all fields
        const fillResponse = await fetch(`${API_BASE}/sessions/${state.sessionId}/fill-all`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fields })
        });

        if (!fillResponse.ok) {
            const error = await fillResponse.json();
            throw new Error(error.detail || 'Failed to save data');
        }

        // Start execution
        const executeResponse = await fetch(`${API_BASE}/sessions/${state.sessionId}/execute`, {
            method: 'POST'
        });

        if (!executeResponse.ok) {
            const error = await executeResponse.json();
            throw new Error(error.detail || 'Failed to start automation');
        }

        hideLoading();
        showView('running');
        
        // CHANGE 1: Show browser visibility notice
        document.getElementById('browserNotice').style.display = 'flex';
        
        // Initialize step tracker
        initializeStepTracker();
        
        // Connect WebSocket and start polling
        connectWebSocket();
        startStatusPolling();

    } catch (error) {
        hideLoading();
        showError(error.message);
    }
}

// VIEW 4: Running Automation with Live Step Tracker
function initializeStepTracker() {
    const tracker = document.getElementById('liveSteps');
    tracker.innerHTML = '<div class="step-item"><span class="step-icon">🚀</span><span>Automation started...</span></div>';
}

function addStepToTracker(icon, text, className = '') {
    const tracker = document.getElementById('liveSteps');
    const step = document.createElement('div');
    step.className = `step-item ${className}`;
    step.innerHTML = `<span class="step-icon">${icon}</span><span>${text}</span>`;
    tracker.appendChild(step);
    tracker.scrollTop = tracker.scrollHeight;
}

function connectWebSocket() {
    const wsUrl = `${WS_BASE}/ws/${state.sessionId}`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('[WebSocket] Connected');
    };

    state.ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    state.ws.onerror = () => {
        console.log('[WebSocket] Error - falling back to polling');
    };

    state.ws.onclose = () => {
        console.log('[WebSocket] Closed');
    };

    // Send ping every 30 seconds to keep connection alive
    setInterval(() => {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send('ping');
        }
    }, 30000);
}

function handleWebSocketMessage(data) {
    const event = data.event;

    // CHANGE 2: Handle different event types
    if (event === 'field_extracted') {
        addStepToTracker('✓', `Auto-filled: ${data.label}`, 'success');
    } else if (event === 'field_filled') {
        addStepToTracker('✓', `Filled: ${data.label || data.field_label}`, 'success');
    } else if (event === 'file_uploaded') {
        addStepToTracker('📎', `Uploaded: ${data.field_label}`, 'success');
    } else if (event === 'file_skipped') {
        addStepToTracker('⚠', `Skipped: ${data.field_label} — ${data.reason}`, 'warning');
    } else if (event === 'captcha_detected') {
        handleCaptchaDetected(data);
    } else if (event === 'status_changed') {
        handleStatusChange(data);
    } else if (event === 'error') {
        showError(data.message);
    }
}

function handleCaptchaDetected(data) {
    addStepToTracker('🤖', 'CAPTCHA detected - waiting for user', 'warning');
    
    const banner = document.getElementById('pauseCaptcha');
    banner.style.display = 'block';
    
    if (data.screenshot_b64) {
        const img = document.getElementById('captchaScreenshot');
        img.src = `data:image/png;base64,${data.screenshot_b64}`;
        img.style.display = 'block';
    }
}

function handleStatusChange(data) {
    const status = data.status;
    const message = data.message;

    // Update timeline
    if (status === 'running') {
        document.getElementById('browserNotice').style.display = 'flex';
        if (message) addStepToTracker('⟳', message);
    } else if (status === 'completed') {
        addStepToTracker('✓', 'Form submitted successfully!', 'success');
        stopStatusPolling();
        setTimeout(() => showComplete(), 1500);
    } else if (status === 'failed') {
        addStepToTracker('✗', `Failed: ${message}`, 'error');
        stopStatusPolling();
    }
}

function startStatusPolling() {
    state.statusPollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/sessions/${state.sessionId}/status`);
            const data = await response.json();
            
            if (data.status === 'completed') {
                stopStatusPolling();
                showComplete();
            } else if (data.status === 'failed') {
                stopStatusPolling();
                showError(data.error || 'Automation failed');
            } else if (data.status === 'paused_captcha') {
                handleCaptchaDetected({ screenshot_b64: data.pause_screenshot });
            } else if (data.status === 'paused_otp') {
                document.getElementById('pauseOtp').style.display = 'block';
            }
        } catch (error) {
            console.error('[Polling] Error:', error);
        }
    }, 3000);
}

function stopStatusPolling() {
    if (state.statusPollInterval) {
        clearInterval(state.statusPollInterval);
        state.statusPollInterval = null;
    }
    if (state.ws) {
        state.ws.close();
        state.ws = null;
    }
}

async function resumeAfterCaptcha() {
    try {
        const response = await fetch(`${API_BASE}/sessions/${state.sessionId}/resume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'captcha' })
        });

        if (!response.ok) {
            throw new Error('Failed to resume');
        }

        document.getElementById('pauseCaptcha').style.display = 'none';
        addStepToTracker('▶', 'Resuming automation...', 'success');

    } catch (error) {
        showError(error.message);
    }
}

async function resumeAfterOtp() {
    const otp = document.getElementById('otpInput').value.trim();
    if (!otp) {
        showError('Please enter the OTP');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/sessions/${state.sessionId}/resume`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: 'otp', value: otp })
        });

        if (!response.ok) {
            throw new Error('Failed to submit OTP');
        }

        document.getElementById('pauseOtp').style.display = 'none';
        document.getElementById('otpInput').value = '';
        addStepToTracker('▶', 'OTP submitted - continuing...', 'success');

    } catch (error) {
        showError(error.message);
    }
}

// VIEW 5: Complete
function showComplete() {
    document.getElementById('completedSessionId').textContent = state.sessionId;
    document.getElementById('completedTime').textContent = new Date().toLocaleString();
    showView('complete');
}

function resetApp() {
    // Stop any running intervals/ws
    stopStatusPolling();

    state.sessionId = null;
    state.dataRequirements = [];
    state.uploadedFiles = [];
    state.documentFields = [];
    state.textFields = [];
    
    document.getElementById('formUrl').value = '';
    document.getElementById('fileInput').value = '';
    fileList.innerHTML = '';
    document.getElementById('btnProcessDocs').style.display = 'none';
    document.getElementById('sessionInfo').style.display = 'none';
    
    showView('start');
}
