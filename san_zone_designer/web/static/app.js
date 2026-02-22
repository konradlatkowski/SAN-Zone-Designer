/* SAN Zone Designer — Frontend Logic (Alpine.js) */

// ── Syntax Highlighting (mirrors colorizer.py) ──
const WWPN_RE = /([0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})/g;
const CISCO_KW = /^(device-alias\s+(?:database|commit|name)|zone\s+name|zoneset\s+(?:name|activate)|vsan\s|config\s+t|member\s|copy\s+running)/i;
const BROCADE_KW = /^(alicreate|zonecreate|cfgcreate|cfgadd|cfgenable|cfgsave|cfgdisable|alidelete|zonedelete|cfgdelete)/i;

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function highlightWwpn(html) {
    return html.replace(WWPN_RE, '<span class="wwpn">$1</span>');
}

function colorizeLine(line, vendor) {
    const stripped = line.trim();
    const escaped = escapeHtml(line);

    if (stripped.startsWith('!') && stripped.includes('---'))
        return `<span class="comment-sep">${escaped}</span>`;
    if (stripped.startsWith('!'))
        return `<span class="comment">${escaped}</span>`;

    if (vendor === 'cisco' && CISCO_KW.test(stripped))
        return highlightWwpn(`<span class="keyword">${escaped}</span>`);
    if (vendor === 'brocade' && BROCADE_KW.test(stripped))
        return highlightWwpn(`<span class="keyword">${escaped}</span>`);

    if (WWPN_RE.test(line))
        return highlightWwpn(escaped);

    return escaped;
}

function colorizeConfig(text, vendor) {
    return text.split('\n').map(l => colorizeLine(l, vendor)).join('\n');
}

// ── Toast Notifications ──
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    const bg = type === 'error' ? 'bg-red-600' : type === 'warning' ? 'bg-yellow-600' : 'bg-green-600';
    toast.className = `toast ${bg} text-white px-4 py-2 rounded-lg shadow-lg mb-2 text-sm`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ── API Helper ──
async function api(url, options = {}) {
    try {
        const res = await fetch(url, options);
        if (res.status === 401) {
            Alpine.store('app').loggedIn = false;
            Alpine.store('app').currentUser = null;
            throw new Error('Session expired');
        }
        const data = await res.json();
        if (!res.ok) {
            const detail = data.detail || `HTTP ${res.status}`;
            showToast(detail, 'error');
            throw new Error(detail);
        }
        return data;
    } catch (e) {
        if (!e.message.includes('HTTP') && e.message !== 'Session expired')
            showToast(e.message, 'error');
        throw e;
    }
}

// ── Download Helper ──
function downloadText(content, filename) {
    const blob = new Blob([content], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
}

// ── Main Alpine Store ──
document.addEventListener('alpine:init', () => {

    Alpine.store('app', {
        // Auth state
        loggedIn: false,
        currentUser: null,
        loginUsername: '',
        loginPassword: '',
        loginError: '',

        // Admin: user management
        showUserModal: false,
        userList: [],
        newUserName: '',
        newUserPassword: '',
        newUserRole: 'user',
        newUserProjects: '',

        // Password change modal
        showPasswordModal: false,
        pwdCurrent: '',
        pwdNew: '',
        pwdConfirm: '',

        // Config tab (Admin only)
        licenseInfo: null,
        newLicenseKey: '',

        // UI
        sidebarOpen: window.innerWidth >= 768,
        appVersion: '',

        // State
        tab: 'generate',
        projects: [],
        showFileModal: false,
        loading: false,
        activeProject: '',

        // Selected files
        selectedInit: '',
        selectedTarget: '',
        selectedExisting: '',

        // Config form
        vendor: 'cisco',
        vsan: 100,
        vsanName: '',
        mode: 'single',
        order: 'ti',
        separator: 'two',
        ifaceRange: '1-32',
        zonesetName: '',
        fabricFilter: '',
        rollback: false,

        // Results
        configOutput: '',
        configHtml: '',
        csvOutput: '',
        rollbackCfg: '',
        zones: [],
        previewData: null,
        diffResult: null,
        lastSavedFiles: [],
        lastWarnings: [],

        // Expand tab
        expandGrid: [],       // [{initiator, targets: [{alias, selected}]}]
        expandPreviewDone: false,

        // Migrate tab
        migrateInput: '',
        migrateType: 'auto',
        migrateProject: '',
        migrateFilename: '',
        migratePreview: null,

        // Logs tab (Admin only)
        logsTab: 'audit',      // 'audit' or 'app'
        auditLogs: [],
        appLogs: [],
        logsLoading: false,
        logsFilterActor: '',
        logsFilterEventType: '',
        logsFilterProject: '',
        logsFilterOutcome: '',
        logsFilterLevel: '',
        logsActors: [],
        logsEventTypes: [],

        // Editor tab
        editorFile: '',          // e.g. "DC_Krakow/initiators.yaml"
        editorFileType: '',      // "initiators" or "targets"
        editorEntries: [],       // [{_id, alias, wwpn, ...}]
        editorDirty: false,
        editorSaving: false,
        editorWarnings: [],
        editorNextId: 1,

        // File modal
        newProjectName: '',
        uploadProject: '',
        filePreview: null,
        modalProjects: [],  // projects with _output/ files for Manage Files modal

        // ── Init ──
        async init() {
            // Load version
            try {
                const vRes = await fetch('/api/version');
                if (vRes.ok) { this.appVersion = (await vRes.json()).version; }
            } catch { /* ignore */ }
            try {
                const res = await fetch('/api/auth/me');
                if (res.ok) {
                    this.currentUser = await res.json();
                    this.loggedIn = true;
                    await this.loadFiles();
                    if (this.currentUser.role === 'admin') {
                        await this.loadLicense();
                    }
                }
            } catch { /* not logged in */ }
            window.addEventListener('beforeunload', (e) => {
                if (this.editorDirty) {
                    e.preventDefault();
                    e.returnValue = '';
                }
            });
            window.addEventListener('resize', () => {
                if (window.innerWidth >= 768) this.sidebarOpen = true;
            });
        },

        // ── Auth ──
        async login() {
            this.loginError = '';
            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: this.loginUsername, password: this.loginPassword }),
                });
                const data = await res.json();
                if (!res.ok) {
                    this.loginError = data.detail || 'Login failed';
                    return;
                }
                this.currentUser = data;
                this.loggedIn = true;
                this.loginUsername = '';
                this.loginPassword = '';
                showToast(`Welcome, ${data.username}`);
                await this.loadFiles();
                if (data.role === 'admin') {
                    await this.loadLicense();
                }
            } catch (e) {
                this.loginError = 'Connection error';
            }
        },

        async logout() {
            try { await fetch('/api/auth/logout', { method: 'POST' }); } catch { }
            this.loggedIn = false;
            this.currentUser = null;
            this.projects = [];
            this.licenseInfo = null;
            this.newLicenseKey = '';
        },

        // ── Change Password ──
        async changePassword() {
            if (!this.pwdCurrent || !this.pwdNew || !this.pwdConfirm) {
                showToast('All fields are required', 'warning');
                return;
            }
            if (this.pwdNew.length < 4) {
                showToast('New password must be at least 4 characters', 'warning');
                return;
            }
            if (this.pwdNew !== this.pwdConfirm) {
                showToast('New passwords do not match', 'warning');
                return;
            }
            try {
                await api('/api/auth/password', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ current_password: this.pwdCurrent, new_password: this.pwdNew }),
                });
                showToast('Password changed successfully!');
                this.showPasswordModal = false;
                this.pwdCurrent = '';
                this.pwdNew = '';
                this.pwdConfirm = '';
            } catch { /* error toast handled by api() */ }
        },

        // ── Admin: User Management ──
        async loadUsers() {
            try {
                this.userList = await api('/api/auth/users');
            } catch { /* handled */ }
        },

        async createUser() {
            const name = this.newUserName.trim();
            const pass = this.newUserPassword.trim();
            if (!name || !pass) { showToast('Username and password required', 'warning'); return; }
            const projects = this.newUserProjects.split(',').map(s => s.trim()).filter(Boolean);
            try {
                await api('/api/auth/users', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username: name, password: pass, role: this.newUserRole, projects }),
                });
                this.newUserName = '';
                this.newUserPassword = '';
                this.newUserRole = 'user';
                this.newUserProjects = '';
                showToast(`User '${name}' created`);
                await this.loadUsers();
            } catch { /* handled */ }
        },

        async deleteUser(username) {
            if (!confirm(`Delete user '${username}'?`)) return;
            try {
                await api(`/api/auth/users/${encodeURIComponent(username)}`, { method: 'DELETE' });
                showToast(`User '${username}' deleted`);
                await this.loadUsers();
            } catch { /* handled */ }
        },

        async updateUserProjects(username, projectsStr) {
            const projects = projectsStr.split(',').map(s => s.trim()).filter(Boolean);
            try {
                await api(`/api/auth/users/${encodeURIComponent(username)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ projects }),
                });
                showToast(`Projects updated for '${username}'`);
                await this.loadUsers();
            } catch { /* handled */ }
        },

        // ── Admin: Configuration ──
        async loadLicense() {
            try {
                const data = await api('/api/config/license');
                if (data.info) {
                    this.licenseInfo = data.info;
                } else if (data.error) {
                    showToast(`License error: ${data.error}`, 'error');
                }
                if (data.license_key) {
                    this.newLicenseKey = data.license_key;
                }
            } catch { /* handled */ }
        },

        async saveLicense() {
            const key = this.newLicenseKey.trim();
            if (!key) {
                showToast("License key cannot be empty", "warning");
                return;
            }
            try {
                const data = await api('/api/config/license', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ license_key: key }),
                });
                showToast("License key saved successfully!");
                this.licenseInfo = data.info;
            } catch { /* Error toasts handled by api() */ }
        },

        // ── Logs Tab ──
        async loadAuditLogs() {
            this.logsLoading = true;
            try {
                const params = new URLSearchParams();
                params.set('limit', '500');
                if (this.logsFilterActor) params.set('actor', this.logsFilterActor);
                if (this.logsFilterEventType) params.set('event_type', this.logsFilterEventType);
                if (this.logsFilterProject) params.set('project', this.logsFilterProject);
                if (this.logsFilterOutcome) params.set('outcome', this.logsFilterOutcome);
                this.auditLogs = (await api(`/api/logs/audit?${params}`)).entries;
            } catch { /* handled */ }
            this.logsLoading = false;
        },

        async loadAppLogs() {
            this.logsLoading = true;
            try {
                const params = new URLSearchParams();
                params.set('limit', '500');
                if (this.logsFilterLevel) params.set('level', this.logsFilterLevel);
                this.appLogs = (await api(`/api/logs/app?${params}`)).entries;
            } catch { /* handled */ }
            this.logsLoading = false;
        },

        async loadLogsMetadata() {
            try {
                const [actors, types] = await Promise.all([
                    api('/api/logs/actors'),
                    api('/api/logs/event-types'),
                ]);
                this.logsActors = actors.actors;
                this.logsEventTypes = types.event_types;
            } catch { /* handled */ }
        },

        async openLogsTab() {
            this.tab = 'logs';
            await this.loadLogsMetadata();
            if (this.logsTab === 'audit') {
                await this.loadAuditLogs();
            } else {
                await this.loadAppLogs();
            }
        },

        formatAuditDetail(detail) {
            if (!detail || Object.keys(detail).length === 0) return '';
            return Object.entries(detail)
                .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
                .join(' | ');
        },

        // ── Files API ──
        async loadFiles() {
            try {
                const data = await api('/api/files/');
                this.projects = data.projects;
            } catch { /* handled by api() */ }
        },

        async loadModalFiles() {
            try {
                const data = await api('/api/files/?include_output=true');
                this.modalProjects = data.projects;
            } catch { /* handled by api() */ }
        },

        async createProject() {
            const name = this.newProjectName.trim();
            if (!name) return;
            try {
                await api('/api/files/project', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name }),
                });
                this.newProjectName = '';
                showToast(`Project '${name}' created`);
                await this.loadFiles();
                await this.loadModalFiles();
            } catch { /* handled */ }
        },

        async uploadFiles(projectName, fileList) {
            if (!fileList.length) return;
            const fd = new FormData();
            for (const f of fileList) fd.append('files', f);
            try {
                await api(`/api/files/upload?project=${encodeURIComponent(projectName)}`, {
                    method: 'POST',
                    body: fd,
                });
                showToast(`Uploaded ${fileList.length} file(s)`);
                await this.loadFiles();
                await this.loadModalFiles();
            } catch { /* handled */ }
        },

        async previewFile(project, filename) {
            try {
                this.filePreview = await api(`/api/files/${encodeURIComponent(project)}/${filename.split('/').map(encodeURIComponent).join('/')}`);
                this.filePreview._project = project;
                this.filePreview._filename = filename;
            } catch { /* handled */ }
        },

        async deleteFile(project, filename) {
            if (!confirm(`Delete ${project}/${filename}?`)) return;
            try {
                await api(`/api/files/${encodeURIComponent(project)}/${filename.split('/').map(encodeURIComponent).join('/')}`, { method: 'DELETE' });
                showToast(`Deleted ${project}/${filename}`);
                this.filePreview = null;
                await this.loadFiles();
                await this.loadModalFiles();
            } catch { /* handled */ }
        },

        async deleteProject(project) {
            if (!confirm(`Delete project '${project}' and ALL its files?`)) return;
            try {
                await api(`/api/files/${encodeURIComponent(project)}`, { method: 'DELETE' });
                showToast(`Deleted project '${project}'`);
                await this.loadFiles();
                await this.loadModalFiles();
            } catch { /* handled */ }
        },

        async downloadFile(project, filename) {
            try {
                const data = await api(`/api/files/${encodeURIComponent(project)}/${filename.split('/').map(encodeURIComponent).join('/')}`);
                const basename = filename.includes('/') ? filename.split('/').pop() : filename;
                downloadText(data.content, basename);
                showToast(`Downloaded ${basename}`);
            } catch { /* handled */ }
        },

        setActiveProject(projectName) {
            if (this.activeProject === projectName) return;
            this.activeProject = projectName;
            // Auto-select first initiator and target files from this project
            const proj = this.projects.find(p => p.name === projectName);
            if (!proj) return;
            const initFile = proj.files.find(f => f.type === 'initiators');
            const tgtFile = proj.files.find(f => f.type === 'targets');
            if (initFile) this.selectedInit = `${projectName}/${initFile.name}`;
            if (tgtFile) this.selectedTarget = `${projectName}/${tgtFile.name}`;
            // Also set migrate project
            this.migrateProject = projectName;
            showToast(`Project: ${projectName}` + (initFile ? ` (init: ${initFile.name})` : '') + (tgtFile ? ` (tgt: ${tgtFile.name})` : ''));
        },

        selectFile(project, filename, type) {
            const path = `${project}/${filename}`;
            if (type === 'initiators') this.selectedInit = path;
            else if (type === 'targets') this.selectedTarget = path;
            else this.selectedExisting = path;
            showToast(`Selected: ${path}`, 'success');
        },

        // ── Request Body Builder ──
        _buildReq() {
            return {
                initiators_path: this.selectedInit,
                targets_path: this.selectedTarget,
                vendor: this.vendor,
                mode: this.mode,
                order: this.order,
                separator: this.separator,
                vsan: parseInt(this.vsan) || 0,
                vsan_name: this.vsanName,
                iface_range: this.ifaceRange,
                zoneset_name: this.zonesetName,
                fabric_filter: this.fabricFilter,
                rollback: this.rollback,
            };
        },

        // ── Generate Tab ──
        async doPreview() {
            if (!this.selectedInit || !this.selectedTarget) {
                showToast('Select initiators and targets files first', 'warning');
                return;
            }
            this.loading = true;
            this.lastWarnings = [];
            try {
                this.previewData = await api('/api/generate/preview', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this._buildReq()),
                });
                this.lastWarnings = this.previewData.warnings || [];
                showToast(`Preview: ${this.previewData.summary.zones} zones`);
            } catch { /* handled */ }
            this.loading = false;
        },

        async doGenerate() {
            if (!this.selectedInit || !this.selectedTarget) {
                showToast('Select initiators and targets files first', 'warning');
                return;
            }
            this.loading = true;
            this.lastWarnings = [];
            try {
                const data = await api('/api/generate/init', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this._buildReq()),
                });
                this.configOutput = data.config;
                this.configHtml = colorizeConfig(data.config, this.vendor);
                this.csvOutput = data.csv;
                this.rollbackCfg = data.rollback_cfg;
                this.zones = data.zones;
                this.lastSavedFiles = data.saved_files || [];
                this.lastWarnings = data.warnings || [];
                showToast(`Generated ${data.summary.zones} zones`);
                if (data.saved_files?.length) showToast(`Saved: ${data.saved_files.join(', ')}`, 'success');
                await this.loadFiles();
            } catch { /* handled */ }
            this.loading = false;
        },

        // ── Expand Tab ──
        async doExpandPreview() {
            if (!this.selectedInit || !this.selectedTarget) {
                showToast('Select initiators and targets files first', 'warning');
                return;
            }
            this.loading = true;
            this.lastWarnings = [];
            try {
                const data = await api('/api/generate/preview', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this._buildReq()),
                });
                this.lastWarnings = data.warnings || [];
                // Build checkbox grid
                const initMap = {};
                for (const z of data.zones) {
                    if (!initMap[z.initiator_alias]) {
                        initMap[z.initiator_alias] = { initiator: z.initiator_alias, targets: new Map() };
                    }
                    for (const ta of z.target_aliases) {
                        initMap[z.initiator_alias].targets.set(ta, false);
                    }
                }
                this.expandGrid = Object.values(initMap).map(row => ({
                    initiator: row.initiator,
                    targets: Array.from(row.targets.keys()).map(t => ({ alias: t, selected: true })),
                }));
                this.expandPreviewDone = true;
                this.previewData = data;
                showToast('Select pairs for generation');
            } catch { /* handled */ }
            this.loading = false;
        },

        async doExpandGenerate() {
            const pairs = [];
            for (const row of this.expandGrid) {
                const selTgts = row.targets.filter(t => t.selected).map(t => t.alias);
                if (selTgts.length > 0) {
                    pairs.push({ initiator: row.initiator, targets: selTgts });
                }
            }
            if (!pairs.length) {
                showToast('No pairs selected', 'warning');
                return;
            }
            this.loading = true;
            this.lastWarnings = [];
            try {
                const req = this._buildReq();
                req.selected_pairs = pairs;
                const data = await api('/api/generate/expand', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(req),
                });
                this.configOutput = data.config;
                this.configHtml = colorizeConfig(data.config, this.vendor);
                this.csvOutput = data.csv;
                this.rollbackCfg = data.rollback_cfg;
                this.zones = data.zones;
                this.lastSavedFiles = data.saved_files || [];
                this.lastWarnings = data.warnings || [];
                showToast(`Generated ${data.summary.zones} zones from selected pairs`);
                if (data.saved_files?.length) showToast(`Saved: ${data.saved_files.join(', ')}`, 'success');
                await this.loadFiles();
            } catch { /* handled */ }
            this.loading = false;
        },

        toggleAllExpand(initIdx, val) {
            this.expandGrid[initIdx].targets.forEach(t => t.selected = val);
        },

        // ── Migrate Tab ──
        async doMigratePreview() {
            if (!this.migrateInput) {
                showToast('Select an input file', 'warning');
                return;
            }
            this.loading = true;
            try {
                this.migratePreview = await api('/api/migrate/preview', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        input_path: this.migrateInput,
                        output_project: this.migrateProject || 'default',
                        output_filename: this.migrateFilename || 'output.yaml',
                        file_type: this.migrateType,
                    }),
                });
                showToast(`Preview: ${this.migratePreview.entry_count} entries`);
            } catch { /* handled */ }
            this.loading = false;
        },

        async doMigrate() {
            if (!this.migrateInput || !this.migrateProject || !this.migrateFilename) {
                showToast('Fill in all fields', 'warning');
                return;
            }
            this.loading = true;
            try {
                const data = await api('/api/migrate/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        input_path: this.migrateInput,
                        output_project: this.migrateProject,
                        output_filename: this.migrateFilename,
                        file_type: this.migrateType,
                    }),
                });
                showToast(`Migrated ${data.count} entries to ${data.output}`);
                if (data.saved_files?.length) showToast(`Saved: ${data.saved_files.join(', ')}`, 'success');
                this.migratePreview = null;
                await this.loadFiles();
            } catch { /* handled */ }
            this.loading = false;
        },

        // ── Diff Tab ──
        async doDiff() {
            if (!this.selectedInit || !this.selectedTarget || !this.selectedExisting) {
                showToast('Select initiators, targets, and existing zone file', 'warning');
                return;
            }
            this.loading = true;
            try {
                const req = this._buildReq();
                req.existing_path = this.selectedExisting;
                this.diffResult = await api('/api/diff/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(req),
                });
                showToast('Diff computed');
                if (this.diffResult.saved_files?.length) showToast(`Saved: ${this.diffResult.saved_files.join(', ')}`, 'success');
                await this.loadFiles();
            } catch { /* handled */ }
            this.loading = false;
        },

        // ── Editor Tab ──
        async loadFileForEdit(path) {
            try {
                const parts = path.split('/');
                const project = parts[0];
                const filename = parts.slice(1).join('/');
                const data = await api(`/api/files/${encodeURIComponent(project)}/${filename.split('/').map(encodeURIComponent).join('/')}`);
                if (data.file_type !== 'initiators' && data.file_type !== 'targets') {
                    showToast('Only initiators/targets YAML files can be edited', 'warning');
                    return;
                }
                this.editorFile = path;
                this.editorFileType = data.file_type;
                this.editorWarnings = data.warnings || [];
                this.editorNextId = 1;
                this.editorEntries = data.entries.map(e => ({ ...e, _id: this.editorNextId++ }));
                this.editorDirty = false;
                this.editorSaving = false;
                this.tab = 'editor';
            } catch { /* handled */ }
        },

        async createEditorFile(fileType) {
            if (!this.activeProject) {
                showToast('Select a project in the sidebar first', 'warning');
                return;
            }
            const filename = fileType + '.yaml';
            const path = `${this.activeProject}/${filename}`;
            try {
                await api(`/api/files/${encodeURIComponent(this.activeProject)}/${encodeURIComponent(filename)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ entries: [], file_type: fileType }),
                });
                showToast(`Created ${filename}`);
                await this.loadFiles();
                await this.loadFileForEdit(path);
            } catch { /* handled */ }
        },

        addEditorEntry() {
            const empty = { _id: this.editorNextId++, alias: '', wwpn: '' };
            if (this.editorFileType === 'initiators') {
                Object.assign(empty, { host: '', fabric: '', vsan_id: 0, description: '' });
            } else {
                Object.assign(empty, { group: '', storage_array: '', port: '', fabric: '', vsan_id: 0, description: '' });
            }
            this.editorEntries.push(empty);
            this.editorDirty = true;
            Alpine.nextTick(() => this.saveEditorFile(true));
        },

        removeEditorEntry(id) {
            this.editorEntries = this.editorEntries.filter(e => e._id !== id);
            this.editorDirty = true;
        },

        markEditorDirty() {
            this.editorDirty = true;
        },

        async saveEditorFile(silent = false) {
            if (!this.editorFile) return;
            this.editorSaving = true;
            const parts = this.editorFile.split('/');
            const project = parts[0];
            const filename = parts.slice(1).join('/');
            // Filter out entries without alias AND wwpn
            const toSave = this.editorEntries
                .filter(e => e.alias?.trim() || e.wwpn?.trim())
                .map(e => {
                    const { _id, ...rest } = e;
                    return rest;
                });
            try {
                const data = await api(`/api/files/${encodeURIComponent(project)}/${filename.split('/').map(encodeURIComponent).join('/')}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ entries: toSave, file_type: this.editorFileType }),
                });
                this.editorDirty = false;
                this.editorWarnings = data.warnings || [];
                if (!silent) showToast(`Saved ${data.entry_count} entries`);
                await this.loadFiles();
            } catch { /* handled */ }
            this.editorSaving = false;
        },

        formatWwpn(entry) {
            const raw = (entry.wwpn || '').replace(/[^0-9a-fA-F]/g, '');
            if (raw.length === 16) {
                entry.wwpn = raw.match(/.{2}/g).join(':').toLowerCase();
                this.markEditorDirty();
            }
        },

        // ── Utilities ──
        copyConfig() {
            navigator.clipboard.writeText(this.configOutput);
            showToast('Config copied to clipboard');
        },
        downloadCfg() {
            downloadText(this.configOutput, 'san_config.cfg');
        },
        downloadCsv() {
            downloadText(this.csvOutput, 'zones.csv');
        },
        downloadRollback() {
            downloadText(this.rollbackCfg, 'rollback.cfg');
        },

        // ── File helpers ──
        getInitiatorFiles() {
            const files = [];
            for (const p of this.projects) {
                for (const file of p.files) {
                    if (file.type === 'initiators') files.push({ path: `${p.name}/${file.name}`, project: p.name, name: file.name });
                }
            }
            return files;
        },
        getTargetFiles() {
            const files = [];
            for (const p of this.projects) {
                for (const file of p.files) {
                    if (file.type === 'targets') files.push({ path: `${p.name}/${file.name}`, project: p.name, name: file.name });
                }
            }
            return files;
        },
        getAllFiles() {
            const files = [];
            for (const p of this.projects) {
                for (const file of p.files) {
                    files.push({ path: `${p.name}/${file.name}`, project: p.name, name: file.name, type: file.type });
                }
            }
            return files;
        },
        getActiveProjectEditorFiles() {
            const proj = this.projects.find(p => p.name === this.activeProject);
            if (!proj) return { initiators: [], targets: [] };
            const initiators = proj.files.filter(f => f.type === 'initiators').map(f => ({ path: `${proj.name}/${f.name}`, name: f.name }));
            const targets = proj.files.filter(f => f.type === 'targets').map(f => ({ path: `${proj.name}/${f.name}`, name: f.name }));
            return { initiators, targets };
        },
        getTxtFiles() {
            const files = [];
            for (const p of this.projects) {
                for (const file of p.files) {
                    if (file.name.endsWith('.txt')) files.push({ path: `${p.name}/${file.name}`, project: p.name, name: file.name });
                }
            }
            return files;
        },
    });
});
