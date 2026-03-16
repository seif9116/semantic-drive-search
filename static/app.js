// ---- State ----
let authenticated = false;
let activeFolderId = null;
let searchTimeout = null;
let eventSource = null;

// ---- DOM refs ----
const $ = (id) => document.getElementById(id);

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    $('searchInput')?.addEventListener('input', onSearchInput);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal(e);
    });
});

// ---- Auth ----
async function checkAuth() {
    try {
        const resp = await fetch('/auth/status');
        const data = await resp.json();
        authenticated = data.authenticated;
        updateAuthUI();
        if (authenticated) {
            loadFolders();
        }
    } catch (e) {
        console.error('Auth check failed:', e);
    }
}

function updateAuthUI() {
    const dot = $('authDot');
    const text = $('authText');
    const btn = $('authBtn');
    const cta = $('ctaSection');
    const workspace = $('workspace');

    if (authenticated) {
        dot.classList.remove('off');
        text.textContent = 'Connected';
        btn.textContent = 'Disconnect';
        cta.classList.add('hidden');
        workspace.classList.remove('hidden');
    } else {
        dot.classList.add('off');
        text.textContent = 'Not connected';
        btn.textContent = 'Connect Drive';
        cta.classList.remove('hidden');
        workspace.classList.add('hidden');
    }
}

async function handleAuth() {
    if (authenticated) {
        await fetch('/auth/logout', { method: 'POST' });
        authenticated = false;
        activeFolderId = null;
        updateAuthUI();
    } else {
        window.location.href = '/auth/login';
    }
}

// ---- Folders ----
async function loadFolders() {
    try {
        const resp = await fetch('/api/folders');
        const folders = await resp.json();
        renderFolders(folders);
    } catch (e) {
        console.error('Failed to load folders:', e);
    }
}

function renderFolders(folders) {
    const section = $('foldersSection');
    const grid = $('foldersGrid');
    const searchSection = $('searchSection');

    if (folders.length === 0) {
        section.classList.add('hidden');
        searchSection.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');
    grid.innerHTML = '';

    folders.forEach((f) => {
        const chip = document.createElement('div');
        chip.className = 'folder-chip' + (f.folder_id === activeFolderId ? ' active' : '');
        chip.innerHTML = `
            <span>${escapeHtml(f.name)}</span>
            <span class="count">${f.file_count} files</span>
            <button class="delete-btn" onclick="event.stopPropagation(); deleteFolder('${f.folder_id}')" title="Remove index">&times;</button>
        `;
        chip.addEventListener('click', () => selectFolder(f.folder_id));
        grid.appendChild(chip);
    });

    // Auto-select first folder if none selected
    if (!activeFolderId && folders.length > 0) {
        selectFolder(folders[0].folder_id);
    } else if (activeFolderId) {
        searchSection.classList.remove('hidden');
    }
}

function selectFolder(folderId) {
    activeFolderId = folderId;
    const searchSection = $('searchSection');
    searchSection.classList.remove('hidden');

    // Update active state
    document.querySelectorAll('.folder-chip').forEach((chip) => {
        chip.classList.remove('active');
    });
    event?.target?.closest?.('.folder-chip')?.classList.add('active');

    // Re-render to update active state properly
    loadFolders();

    // Clear previous results
    $('resultsSection').classList.add('hidden');
    $('emptyState').classList.add('hidden');
    $('searchInput').value = '';
    $('searchHint').textContent = `Searching in folder: ${folderId.substring(0, 12)}...`;
}

async function deleteFolder(folderId) {
    try {
        await fetch(`/api/folders/${folderId}`, { method: 'DELETE' });
        if (activeFolderId === folderId) {
            activeFolderId = null;
            $('searchSection').classList.add('hidden');
            $('resultsSection').classList.add('hidden');
        }
        loadFolders();
    } catch (e) {
        console.error('Failed to delete folder:', e);
    }
}

// ---- Indexing ----
async function startIndexing() {
    const input = $('folderInput');
    const folderId = input.value.trim();
    if (!folderId) return;

    const btn = $('indexBtn');
    btn.disabled = true;
    btn.textContent = 'Starting...';

    try {
        const resp = await fetch('/api/index', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_id: folderId }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            alert(err.detail || 'Failed to start indexing');
            btn.disabled = false;
            btn.textContent = 'Index';
            return;
        }

        const data = await resp.json();
        const resolvedId = data.folder_id;
        input.value = '';

        // Show progress
        showProgress(resolvedId);
    } catch (e) {
        console.error('Indexing failed:', e);
        alert('Failed to start indexing');
        btn.disabled = false;
        btn.textContent = 'Index';
    }
}

function showProgress(folderId) {
    const section = $('progressSection');
    section.classList.remove('hidden');

    const btn = $('indexBtn');
    btn.disabled = true;
    btn.textContent = 'Indexing...';

    // Use SSE for live updates
    if (eventSource) eventSource.close();

    eventSource = new EventSource(`/api/index/status-stream/${folderId}`);

    eventSource.onmessage = (event) => {
        const status = JSON.parse(event.data);
        updateProgress(status);

        if (status.status === 'complete' || status.status === 'error') {
            eventSource.close();
            eventSource = null;
            btn.disabled = false;
            btn.textContent = 'Index';

            if (status.status === 'complete') {
                setTimeout(() => {
                    section.classList.add('hidden');
                    activeFolderId = folderId;
                    loadFolders();
                }, 1500);
            }
        }
    };

    eventSource.onerror = () => {
        // Fall back to polling
        eventSource.close();
        eventSource = null;
        pollProgress(folderId);
    };
}

async function pollProgress(folderId) {
    const section = $('progressSection');
    const btn = $('indexBtn');

    const poll = async () => {
        try {
            const resp = await fetch(`/api/index/status/${folderId}`);
            const status = await resp.json();
            updateProgress(status);

            if (status.status === 'complete' || status.status === 'error') {
                btn.disabled = false;
                btn.textContent = 'Index';
                if (status.status === 'complete') {
                    setTimeout(() => {
                        section.classList.add('hidden');
                        activeFolderId = folderId;
                        loadFolders();
                    }, 1500);
                }
                return;
            }

            setTimeout(poll, 1500);
        } catch (e) {
            setTimeout(poll, 3000);
        }
    };

    poll();
}

function updateProgress(status) {
    const total = status.total_files || 0;
    const processed = status.processed || 0;
    const failed = status.failed || 0;
    const pct = total > 0 ? Math.round(((processed + failed) / total) * 100) : 0;

    $('progressBar').style.width = pct + '%';
    $('progressStats').textContent = `${processed + failed} / ${total}` + (failed > 0 ? ` (${failed} failed)` : '');
    $('progressFile').textContent = status.current_file || '';

    if (status.status === 'complete') {
        $('progressLabel').textContent = 'Complete!';
        $('progressLabel').classList.remove('loading-pulse');
        $('progressBar').style.width = '100%';
    } else if (status.status === 'error') {
        $('progressLabel').textContent = 'Error';
        $('progressLabel').classList.remove('loading-pulse');
    } else {
        $('progressLabel').textContent = 'Indexing...';
    }
}

// ---- Search ----
function onSearchInput(e) {
    const query = e.target.value.trim();

    if (searchTimeout) clearTimeout(searchTimeout);

    if (!query) {
        $('resultsSection').classList.add('hidden');
        $('emptyState').classList.add('hidden');
        return;
    }

    searchTimeout = setTimeout(() => performSearch(query), 300);
}

async function performSearch(query) {
    if (!activeFolderId) return;

    try {
        const params = new URLSearchParams({
            q: query,
            folder_id: activeFolderId,
            limit: '20',
        });

        const resp = await fetch(`/api/search?${params}`);

        if (!resp.ok) {
            if (resp.status === 401) {
                authenticated = false;
                updateAuthUI();
                return;
            }
            console.error('Search failed:', resp.status);
            return;
        }

        const data = await resp.json();
        renderResults(data);
    } catch (e) {
        console.error('Search error:', e);
    }
}

function renderResults(data) {
    const section = $('resultsSection');
    const grid = $('resultsGrid');
    const empty = $('emptyState');
    const count = $('resultsCount');

    if (data.results.length === 0) {
        section.classList.add('hidden');
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');
    section.classList.remove('hidden');
    count.textContent = `${data.results.length} result${data.results.length !== 1 ? 's' : ''} for "${data.query}"`;

    grid.innerHTML = '';

    data.results.forEach((r) => {
        const card = document.createElement('div');
        card.className = 'result-card';

        const simPct = Math.round(r.similarity * 100);
        const isVideo = r.mime_type.startsWith('video/');

        card.innerHTML = `
            <div class="image-wrap">
                ${isVideo
                    ? `<video src="${r.thumbnail_url}" muted preload="metadata" style="width:100%;height:100%;object-fit:cover;"></video>`
                    : `<img src="${r.thumbnail_url}" alt="${escapeHtml(r.name)}" loading="lazy" />`
                }
                <span class="similarity-badge">${simPct}%</span>
            </div>
            <div class="card-info">
                <div class="file-name" title="${escapeHtml(r.name)}">${escapeHtml(r.name)}</div>
                <div class="file-type">${r.mime_type}</div>
            </div>
        `;

        card.addEventListener('click', () => openModal(r));
        grid.appendChild(card);
    });
}

// ---- Modal ----
function openModal(result) {
    const modal = $('modal');
    const img = $('modalImg');
    const info = $('modalInfo');

    const isVideo = result.mime_type.startsWith('video/');
    const mediaUrl = `/api/media/${result.file_id}`;

    if (isVideo) {
        img.style.display = 'none';
        // Replace img with video temporarily
        let video = modal.querySelector('video.modal-video');
        if (!video) {
            video = document.createElement('video');
            video.className = 'modal-video';
            video.controls = true;
            video.style.maxWidth = '100%';
            video.style.maxHeight = '80vh';
            video.style.borderRadius = 'var(--radius)';
            video.style.boxShadow = '0 25px 80px rgba(0,0,0,0.5)';
            img.parentNode.insertBefore(video, img);
        }
        video.src = mediaUrl;
        video.style.display = 'block';
    } else {
        let video = modal.querySelector('video.modal-video');
        if (video) video.style.display = 'none';
        img.style.display = 'block';
        img.src = mediaUrl;
        img.alt = result.name;
    }

    const simPct = Math.round(result.similarity * 100);
    info.textContent = `${result.name} \u2014 ${simPct}% match`;

    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
}

function closeModal(e) {
    if (e && e.target !== $('modal') && e.target !== e.currentTarget) return;
    const modal = $('modal');
    modal.classList.remove('open');
    document.body.style.overflow = '';

    // Stop video if playing
    const video = modal.querySelector('video.modal-video');
    if (video) {
        video.pause();
        video.src = '';
    }
}

// ---- Utils ----
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
