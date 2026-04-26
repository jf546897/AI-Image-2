const MAX_PROMPT_CHARS = 4000;

const DEFAULT_PROMPT = `Masterpiece, best quality, ultra realistic, 8k resolution, cinematic lighting. Interior of a very old and cold medieval European room, top-down wide shot. Keep the room layout consistent with the reference images: rough medieval wooden bed, purple coarse blanket, rope coil on bed, peeling plaster wall, ancient stone wall, broken arched wooden window, snowstorm and cold blue night outside. Blue cold wind enters through the window, realistic ice crystals and dust particles in the air. Keep character positions and proportions based on uploaded references. Cinematic composition and realistic textures.`;

const TEXT = {
    textMode: 'Text to Image',
    imageMode: 'Image to Image',
    maskMode: 'Masked Edit',
    waiting: 'Ready',
    running: 'Generating...',
    failed: 'Failed',
    start: 'Generate Image',
};

const STAGE_TEXT = {
    queued: 'Queued',
    prepare: 'Preparing',
    connect: 'Connecting GPT Image 2',
    generating_text: 'Generating image',
    generating_edit: 'Editing image',
    completed: 'Completed',
    failed: 'Failed',
};

const MESSAGE_TEXT = {
    task_created: 'Task created, waiting for server',
    task_created_images_cached: 'Task created, reference images cached',
    prepare_request: 'Preparing prompt, images and options',
    connect_gateway: 'Connecting to image gateway',
    image2_generating: 'GPT Image 2 is generating. Usually 20-120 seconds.',
    image2_editing: 'GPT Image 2 is using references. Complex jobs may take 60-300 seconds.',
    responses_in_progress: 'Streaming image job has started.',
    responses_generating: 'Image model is generating.',
    responses_partial_image: 'Received image preview from stream.',
    responses_completed: 'Stream completed, preparing result.',
    completed: 'Completed',
    failed: 'Failed',
};

const state = {
    imageFiles: [],
    maskFile: null,
    progressTimer: null,
    taskStartedAt: null,
    lastDisplayedProgress: 0,
};

const el = {
    form: document.getElementById('image-form'),
    prompt: document.getElementById('prompt'),
    promptCount: document.getElementById('prompt-count'),
    size: document.getElementById('size'),
    quality: document.getElementById('quality'),
    background: document.getElementById('background'),
    outputFormat: document.getElementById('output-format'),
    outputCompression: document.getElementById('output-compression'),
    imageDropZone: document.getElementById('image-drop-zone'),
    maskDropZone: document.getElementById('mask-drop-zone'),
    imageFile: document.getElementById('image-file'),
    maskFile: document.getElementById('mask-file'),
    imagePreviewList: document.getElementById('image-preview-list'),
    maskPreview: document.getElementById('mask-preview'),
    generateBtn: document.getElementById('generate-btn'),
    clearBtn: document.getElementById('clear-btn'),
    settingsToggle: document.getElementById('settings-toggle'),
    settingsPanel: document.getElementById('settings-panel'),
    configBadge: document.getElementById('config-badge'),
    apiBaseUrl: document.getElementById('api-base-url'),
    apiKey: document.getElementById('api-key'),
    apiConfigStatus: document.getElementById('api-config-status'),
    saveApiConfigBtn: document.getElementById('save-api-config-btn'),
    resultStatus: document.getElementById('result-status'),
    emptyResult: document.getElementById('empty-result'),
    summaryPrompt: document.getElementById('summary-prompt'),
    summaryImages: document.getElementById('summary-images'),
    resultList: document.getElementById('result-list'),
    historyStrip: document.getElementById('history-strip'),
    toastRoot: document.getElementById('toast-root'),
    pageDropOverlay: document.getElementById('page-drop-overlay'),
    pageDropTitle: document.getElementById('page-drop-title'),
    pageDropSubtitle: document.getElementById('page-drop-subtitle'),
    progressPanel: document.getElementById('progress-panel'),
    progressStage: document.getElementById('progress-stage'),
    progressPercent: document.getElementById('progress-percent'),
    progressBar: document.getElementById('progress-bar'),
    progressMessage: document.getElementById('progress-message'),
    progressElapsed: document.getElementById('progress-elapsed'),
};

function toast(message, type = 'info') {
    const item = document.createElement('div');
    item.className = `toast ${type}`;
    item.textContent = message;
    el.toastRoot.appendChild(item);
    setTimeout(() => item.remove(), 4200);
}

function imageOnly(files) {
    return Array.from(files || []).filter((file) => file.type.startsWith('image/'));
}

function currentMode() {
    if (state.maskFile) return 'mask';
    if (state.imageFiles.length) return 'image';
    return 'text';
}

function getModeLabel() {
    const mode = currentMode();
    if (mode === 'mask') return TEXT.maskMode;
    if (mode === 'image') return TEXT.imageMode;
    return TEXT.textMode;
}

function updatePromptCount() {
    if (!el.promptCount) return;
    const length = el.prompt.value.length;
    const suffix = length > MAX_PROMPT_CHARS ? ' - will auto-optimize' : '';
    el.promptCount.textContent = `${length} / ${MAX_PROMPT_CHARS}${suffix}`;
    el.promptCount.classList.toggle('over-limit', length > MAX_PROMPT_CHARS);
    el.prompt.classList.toggle('over-limit', length > MAX_PROMPT_CHARS);
    updateInputSummary();
}

function optimizePromptToLimit(prompt) {
    const compact = String(prompt || '')
        .replace(/\r\n/g, '\n')
        .replace(/[ \t]+/g, ' ')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
    if (compact.length <= MAX_PROMPT_CHARS) return compact;

    const budget = MAX_PROMPT_CHARS - 120;
    const headLength = Math.floor(budget * 0.72);
    const tailLength = Math.max(0, budget - headLength);
    const head = compact.slice(0, headLength).replace(/[???,.!???:][^???,.!???:]*$/, '');
    const tail = compact.slice(-tailLength);
    return `${head}\n\n[Auto-optimized: middle repetitive details compressed to fit the 4000 character limit.]\n\n${tail}`.slice(0, MAX_PROMPT_CHARS);
}

function updateInputSummary() {
    if (!el.summaryPrompt || !el.summaryImages) return;
    const prompt = el.prompt.value.trim();
    el.summaryPrompt.textContent = prompt || 'Prompt will appear here.';
    el.summaryImages.innerHTML = '';
    state.imageFiles.forEach((file, index) => {
        const image = document.createElement('img');
        image.src = URL.createObjectURL(file);
        image.alt = `Reference ${index + 1}`;
        el.summaryImages.appendChild(image);
    });
    if (state.maskFile) {
        const mask = document.createElement('img');
        mask.src = URL.createObjectURL(state.maskFile);
        mask.alt = 'Mask';
        mask.className = 'mask-summary-image';
        el.summaryImages.appendChild(mask);
    }
}

function addImageFiles(files) {
    const incoming = imageOnly(files);
    if (!incoming.length) {
        toast('Please drop image files.', 'error');
        return;
    }
    const existingKeys = new Set(state.imageFiles.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
    incoming.slice(0, 16 - state.imageFiles.length).forEach((file) => {
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (!existingKeys.has(key)) {
            state.imageFiles.push(file);
            existingKeys.add(key);
        }
    });
    renderImagePreviews();
    updateInputSummary();
}

function moveReferenceImage(index, direction) {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= state.imageFiles.length) return;
    const [file] = state.imageFiles.splice(index, 1);
    state.imageFiles.splice(targetIndex, 0, file);
    renderImagePreviews();
    updateInputSummary();
}

function setMaskFile(files) {
    const incoming = imageOnly(files);
    state.maskFile = incoming[0] || null;
    if (!state.maskFile) {
        el.maskPreview.classList.add('hidden');
        el.maskPreview.removeAttribute('src');
        updateInputSummary();
        return;
    }
    el.maskPreview.src = URL.createObjectURL(state.maskFile);
    el.maskPreview.classList.remove('hidden');
    updateInputSummary();
}

function renderImagePreviews() {
    el.imagePreviewList.innerHTML = '';
    state.imageFiles.forEach((file, index) => {
        const card = document.createElement('div');
        card.className = 'preview-card';
        const image = document.createElement('img');
        image.src = URL.createObjectURL(file);
        image.alt = file.name || `Reference ${index + 1}`;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = 'x';
        remove.title = 'Remove';
        remove.className = 'preview-remove';
        remove.addEventListener('click', () => {
            state.imageFiles.splice(index, 1);
            renderImagePreviews();
            updateInputSummary();
        });
        const controls = document.createElement('div');
        controls.className = 'preview-order';
        const up = document.createElement('button');
        up.type = 'button';
        up.textContent = '↑';
        up.title = 'Move earlier';
        up.disabled = index === 0;
        up.addEventListener('click', () => moveReferenceImage(index, -1));
        const down = document.createElement('button');
        down.type = 'button';
        down.textContent = '↓';
        down.title = 'Move later';
        down.disabled = index === state.imageFiles.length - 1;
        down.addEventListener('click', () => moveReferenceImage(index, 1));
        controls.append(up, down);
        const badge = document.createElement('span');
        badge.textContent = `#${index + 1}`;
        card.append(image, remove, controls, badge);
        el.imagePreviewList.appendChild(card);
    });
}

function bindDropZone(dropZone, callback) {
    dropZone.addEventListener('click', () => {
        const input = dropZone.querySelector('input[type="file"]');
        if (input) input.click();
    });
    ['dragenter', 'dragover'].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = 'copy';
            dropZone.classList.add('dragover');
        });
    });
    ['dragleave', 'drop'].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.remove('dragover');
        });
    });
    dropZone.addEventListener('drop', (event) => callback(event.dataTransfer.files));
}

function hasImageFiles(dataTransfer) {
    if (!dataTransfer) return false;
    const types = Array.from(dataTransfer.types || []);
    if (types.includes('Files')) return true;
    return Array.from(dataTransfer.items || []).some((item) => item.kind === 'file' && item.type.startsWith('image/'));
}

function showPageDropOverlay() {
    document.body.classList.add('page-dragging');
    el.pageDropOverlay.classList.remove('hidden');
}

function hidePageDropOverlay() {
    document.body.classList.remove('page-dragging');
    el.pageDropOverlay.classList.add('hidden');
}

function bindPageDropTarget() {
    let dragDepth = 0;
    ['dragenter', 'dragover', 'drop'].forEach((eventName) => {
        window.addEventListener(eventName, (event) => {
            if (!hasImageFiles(event.dataTransfer)) return;
            event.preventDefault();
            event.stopPropagation();
            event.dataTransfer.dropEffect = 'copy';
        }, { capture: true });
    });
    window.addEventListener('dragenter', (event) => {
        if (!hasImageFiles(event.dataTransfer)) return;
        dragDepth += 1;
        showPageDropOverlay();
    }, { capture: true });
    window.addEventListener('dragleave', (event) => {
        if (!hasImageFiles(event.dataTransfer)) return;
        dragDepth = Math.max(0, dragDepth - 1);
        if (dragDepth === 0 || event.clientX <= 0 || event.clientY <= 0 || event.clientX >= window.innerWidth || event.clientY >= window.innerHeight) hidePageDropOverlay();
    }, { capture: true });
    window.addEventListener('drop', (event) => {
        if (!hasImageFiles(event.dataTransfer)) return;
        dragDepth = 0;
        hidePageDropOverlay();
        addImageFiles(event.dataTransfer.files);
    }, { capture: true });
    window.addEventListener('blur', () => {
        dragDepth = 0;
        hidePageDropOverlay();
    });
}

function appendCommonFormData(formData) {
    formData.append('prompt', el.prompt.value.trim());
    formData.append('size', el.size.value);
    formData.append('quality', el.quality.value);
    formData.append('background', el.background.value);
    formData.append('output_format', el.outputFormat.value);
    const compression = Number.parseInt(el.outputCompression.value, 10);
    if (!Number.isNaN(compression)) formData.append('output_compression', String(compression));
}

function addHistoryImage(src) {
    if (!el.historyStrip) return;
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'history-item';
    item.innerHTML = `<img src="${src}" alt="History result"><span>Now</span>`;
    item.addEventListener('click', () => window.open(src, '_blank'));
    el.historyStrip.prepend(item);
    while (el.historyStrip.children.length > 8) el.historyStrip.lastElementChild.remove();
}

function renderResults(data) {
    const items = Array.isArray(data.data) ? data.data : [];
    el.resultList.innerHTML = '';
    el.emptyResult.classList.toggle('hidden', items.length > 0);
    items.forEach((item, index) => {
        const b64 = item.b64_json || item.image_base64 || item.result;
        if (!b64) return;
        const format = el.outputFormat.value || 'png';
        const src = b64.startsWith('data:') ? b64 : `data:image/${format};base64,${b64}`;
        const card = document.createElement('article');
        card.className = 'result-card';
        card.innerHTML = `<img src="${src}" alt="Generated result ${index + 1}"><div class="result-meta"><span>${getModeLabel()}</span><a href="${src}" download="ai-image2-${Date.now()}-${index + 1}.${format}">Download</a></div>`;
        el.resultList.appendChild(card);
        addHistoryImage(src);
    });
    el.resultStatus.textContent = items.length ? `Generated ${items.length}` : 'No image returned';
}

function stageLabel(stage) {
    return STAGE_TEXT[stage] || stage || 'Processing';
}

function messageLabel(message) {
    return MESSAGE_TEXT[message] || message || 'Processing';
}

function smoothProgress(progress, stage, status) {
    if (status === 'completed' || status === 'failed') return 100;
    const numeric = Number(progress);
    if (Number.isNaN(numeric)) return 0;
    return Math.max(0, Math.min(99, numeric));
}

function setProgress(progress, stage, message, status = 'running') {
    const displayed = smoothProgress(progress, stage, status);
    el.progressPanel.classList.remove('hidden');
    el.progressStage.textContent = stageLabel(stage);
    el.progressPercent.textContent = status === 'completed' ? '100%' : status === 'failed' ? 'Failed' : `${Math.round(displayed)}%`;
    el.progressBar.style.width = `${status === 'failed' ? 100 : displayed}%`;
    el.progressMessage.textContent = messageLabel(message);
    if (state.taskStartedAt) el.progressElapsed.textContent = `${Math.floor((Date.now() - state.taskStartedAt) / 1000)}s elapsed`;
}

async function pollTask(taskId) {
    if (state.progressTimer) clearInterval(state.progressTimer);
    state.taskStartedAt = Date.now();
    state.lastDisplayedProgress = 0;
    setProgress(0, 'queued', 'task_created');
    state.progressTimer = setInterval(async () => {
        try {
            const response = await fetch(`/api/tasks/${taskId}`, { cache: 'no-store' });
            const task = await response.json();
            if (!response.ok) throw new Error(task.detail || `HTTP ${response.status}`);
            setProgress(task.progress, task.stage, task.message, task.status);
            if (task.status === 'completed') {
                clearInterval(state.progressTimer);
                renderResults(task.result || { data: [] });
                setProgress(100, 'completed', 'completed', 'completed');
                toast('Image generated.');
                el.generateBtn.disabled = false;
                el.generateBtn.textContent = TEXT.start;
            }
            if (task.status === 'failed') {
                clearInterval(state.progressTimer);
                el.resultStatus.textContent = TEXT.failed;
                const errorMessage = task.error || task.message || TEXT.failed;
                toast(errorMessage, 'error');
                setProgress(100, 'failed', errorMessage, 'failed');
                el.generateBtn.disabled = false;
                el.generateBtn.textContent = TEXT.start;
            }
        } catch (error) {
            clearInterval(state.progressTimer);
            toast(error.message || 'Progress polling failed.', 'error');
            el.generateBtn.disabled = false;
            el.generateBtn.textContent = TEXT.start;
        }
    }, 1000);
}

async function submitRequest(event) {
    event.preventDefault();
    el.imageFile.removeAttribute('required');
    el.maskFile.removeAttribute('required');
    if (!el.prompt.value.trim()) {
        toast('Please enter a prompt.', 'error');
        return;
    }
    if (el.prompt.value.length > MAX_PROMPT_CHARS) {
        el.prompt.value = optimizePromptToLimit(el.prompt.value);
        updatePromptCount();
        toast(`Prompt auto-optimized to ${el.prompt.value.length} characters.`);
    }
    if (state.maskFile && !state.imageFiles.length) {
        toast('Mask requires a reference image first.', 'error');
        return;
    }
    const formData = new FormData();
    appendCommonFormData(formData);
    let endpoint = '/api/tasks/generate';
    if (state.imageFiles.length) {
        endpoint = '/api/tasks/edit';
        state.imageFiles.forEach((file) => formData.append('image', file));
        if (state.maskFile) formData.append('mask', state.maskFile);
    }
    el.generateBtn.disabled = true;
    el.generateBtn.textContent = TEXT.running;
    el.resultStatus.textContent = `${getModeLabel()} running`;
    el.resultList.innerHTML = '';
    el.emptyResult.classList.remove('hidden');
    try {
        const response = await fetch(endpoint, { method: 'POST', body: formData });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
        pollTask(data.task_id);
    } catch (error) {
        el.resultStatus.textContent = TEXT.failed;
        toast(error.message || TEXT.failed, 'error');
        el.generateBtn.disabled = false;
        el.generateBtn.textContent = TEXT.start;
    }
}

function clearResults() {
    if (state.progressTimer) clearInterval(state.progressTimer);
    state.imageFiles = [];
    state.maskFile = null;
    renderImagePreviews();
    setMaskFile([]);
    el.resultList.innerHTML = '';
    el.emptyResult.classList.remove('hidden');
    el.progressPanel.classList.add('hidden');
    el.resultStatus.textContent = TEXT.waiting;
    updateInputSummary();
}

async function loadConfig() {
    try {
        const response = await fetch('/api/config', { cache: 'no-store' });
        const config = await response.json();
        const keyText = config.key_hint ? ` | Key ${config.key_hint}` : '';
        el.configBadge.textContent = `${config.model} | ${config.base_url}${keyText}`;
        el.configBadge.classList.toggle('warning', !config.has_api_key);
        el.configBadge.title = config.has_api_key ? 'API key loaded' : 'API key missing';
        if (el.apiBaseUrl) el.apiBaseUrl.value = config.base_url || '';
        if (el.apiConfigStatus) el.apiConfigStatus.textContent = config.has_api_key ? `Ready (${config.config_source || 'config'})` : 'Enter URL and Key';
    } catch (error) {
        el.configBadge.textContent = 'Config load failed';
        el.configBadge.classList.add('warning');
        if (el.apiConfigStatus) el.apiConfigStatus.textContent = 'Config load failed';
    }
}

async function saveApiConfig() {
    const baseUrl = (el.apiBaseUrl?.value || '').trim();
    const apiKey = (el.apiKey?.value || '').trim();
    if (!baseUrl || !apiKey) {
        toast('Please enter API URL Base and API Key.', 'error');
        return;
    }

    el.saveApiConfigBtn.disabled = true;
    el.saveApiConfigBtn.textContent = 'Saving...';
    try {
        const response = await fetch('/api/local-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ base_url: baseUrl, api_key: apiKey }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
        el.apiKey.value = '';
        toast('API settings saved.');
        await loadConfig();
    } catch (error) {
        toast(error.message || 'Failed to save API settings.', 'error');
    } finally {
        el.saveApiConfigBtn.disabled = false;
        el.saveApiConfigBtn.textContent = 'Save';
    }
}

function setSettingsExpanded(expanded) {
    if (!el.settingsToggle || !el.settingsPanel) return;
    el.settingsPanel.classList.toggle('hidden', !expanded);
    el.settingsToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    el.settingsToggle.textContent = expanded ? '\u6536\u8d77\u8bbe\u7f6e' : '\u8bbe\u7f6e';
}

function toggleSettings() {
    if (!el.settingsPanel) return;
    setSettingsExpanded(el.settingsPanel.classList.contains('hidden'));
}

function updateViewportMode() {
    document.body.classList.toggle('compact-height', window.innerHeight < 820);
    document.body.classList.toggle('ultra-compact-height', window.innerHeight < 700);
}

function initDefaults() {
    el.pageDropTitle.textContent = '\u677e\u5f00\u9f20\u6807\uff0c\u6dfb\u52a0\u4e3a\u53c2\u8003\u56fe';
    el.pageDropSubtitle.textContent = '\u6574\u4e2a\u9875\u9762\u90fd\u53ef\u4ee5\u63a5\u6536\u62d6\u5165\u7684\u56fe\u7247';
    if (!el.prompt.value.trim() || el.prompt.value.trim() === '?') el.prompt.value = DEFAULT_PROMPT;
    el.prompt.placeholder = 'Describe the image you want to generate or edit.';
    el.resultStatus.textContent = TEXT.waiting;
    updatePromptCount();
    updateInputSummary();
}

document.addEventListener('DOMContentLoaded', () => {
    updateViewportMode();
    initDefaults();
    el.prompt.addEventListener('input', updatePromptCount);
    el.imageFile.addEventListener('change', () => addImageFiles(el.imageFile.files));
    el.maskFile.addEventListener('change', () => setMaskFile(el.maskFile.files));
    bindDropZone(el.imageDropZone, addImageFiles);
    bindDropZone(el.maskDropZone, setMaskFile);
    bindPageDropTarget();
    el.form.addEventListener('submit', submitRequest);
    el.clearBtn.addEventListener('click', clearResults);
    if (el.settingsToggle) el.settingsToggle.addEventListener('click', toggleSettings);
    if (el.saveApiConfigBtn) el.saveApiConfigBtn.addEventListener('click', saveApiConfig);
    setSettingsExpanded(false);
    loadConfig();
    window.addEventListener('resize', updateViewportMode);
});
