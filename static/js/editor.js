class ModernFileEditor {
    constructor() {
        this.editors = new Map();
        this.activeTab = null;
        this.unsavedFiles = new Set();
        this.settings = this.loadSettings();
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.sidebarOpen = window.innerWidth > 768;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        this.applySettings();
        this.setupMobileOptimizations();
        this.setupTheme();
    }

    setupTheme() {
        const theme = this.settings.theme || 'monokai';
        document.documentElement.className = `editor-theme-${theme}`;
    }

    loadSettings() {
        const defaults = {
            theme: 'monokai',
            fontSize: 14,
            tabSize: 4,
            wordWrap: true,
            lineNumbers: true,
            autoSave: true,
            autoSaveDelay: 2000
        };
        
        const saved = localStorage.getItem('editor-settings');
        return saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
    }

    saveSettings() {
        localStorage.setItem('editor-settings', JSON.stringify(this.settings));
    }

    applySettings() {
        document.documentElement.style.setProperty('--editor-font-size', `${this.settings.fontSize}px`);
        
        // Apply to all existing editors
        this.editors.forEach(editor => {
            editor.setOption('theme', this.settings.theme);
            editor.setOption('lineNumbers', this.settings.lineNumbers);
            editor.setOption('lineWrapping', this.settings.wordWrap);
            editor.setOption('indentUnit', this.settings.tabSize);
            editor.refresh();
        });
    }

    setupEventListeners() {
        // Tab management
        document.addEventListener('click', (e) => {
            if (e.target.matches('.tab-close')) {
                e.stopPropagation();
                this.closeTab(e.target.dataset.path);
            } else if (e.target.matches('.editor-tab') || e.target.closest('.editor-tab')) {
                const tab = e.target.closest('.editor-tab');
                this.switchTab(tab.dataset.path);
            }
        });

        // File tree interactions
        document.addEventListener('click', (e) => {
            if (e.target.matches('.tree-file')) {
                this.openFile(e.target.dataset.path);
            } else if (e.target.matches('.folder-toggle')) {
                this.toggleFolder(e.target.closest('.tree-item'));
            }
        });

        // Context menu
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.tree-item')) {
                e.preventDefault();
                this.showContextMenu(e, e.target.closest('.tree-item'));
            }
        });

        // Auto-save
        if (this.settings.autoSave) {
            this.setupAutoSave();
        }

        // Settings modal
        document.addEventListener('click', (e) => {
            if (e.target.matches('#settings-btn')) {
                this.showSettingsModal();
            }
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Save: Ctrl+S / Cmd+S
            if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                e.preventDefault();
                this.saveActiveFile();
            }
            
            // Find: Ctrl+F / Cmd+F
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                e.preventDefault();
                this.showSearchDialog();
            }
            
            // Close tab: Ctrl+W / Cmd+W
            if ((e.ctrlKey || e.metaKey) && e.key === 'w') {
                e.preventDefault();
                if (this.activeTab) {
                    this.closeTab(this.activeTab);
                }
            }
            
            // New file: Ctrl+N / Cmd+N
            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                this.showCreateModal('file');
            }
        });
    }

    setupMobileOptimizations() {
        if (window.innerWidth <= 768) {
            // Mobile-specific optimizations
            this.settings.fontSize = Math.max(this.settings.fontSize, 16);
            this.applySettings();
            
            // Setup mobile gestures
            this.setupMobileGestures();
        }
    }

    setupMobileGestures() {
        let touchStartX = 0;
        let touchStartY = 0;
        
        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        });
        
        document.addEventListener('touchend', (e) => {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;
            
            // Swipe gestures for tab navigation
            if (Math.abs(deltaX) > 100 && Math.abs(deltaY) < 50) {
                if (deltaX > 0) {
                    this.switchToPreviousTab();
                } else {
                    this.switchToNextTab();
                }
            }
        });
    }

    openFile(filePath) {
        if (this.editors.has(filePath)) {
            this.switchTab(filePath);
            return;
        }

        this.showLoadingIndicator();
        
        fetch(`/bot/${window.botIndex}/edit?path=${encodeURIComponent(filePath)}`, {
            headers: { 'HX-Request': 'true' }
        })
        .then(response => response.text())
        .then(html => {
            this.hideLoadingIndicator();
            this.createTab(filePath, html);
            this.switchTab(filePath);
        })
        .catch(error => {
            this.hideLoadingIndicator();
            this.showToast('Failed to load file', 'error');
            console.error('Error loading file:', error);
        });
    }

    createTab(filePath, content) {
        // Create tab element
        const tabsContainer = document.querySelector('.editor-tabs');
        const tab = document.createElement('div');
        tab.className = 'editor-tab';
        tab.dataset.path = filePath;
        
        const fileName = filePath.split('/').pop();
        tab.innerHTML = `
            <span class="tab-name">${fileName}</span>
            <span class="tab-unsaved hidden">●</span>
            <button class="tab-close" data-path="${filePath}">×</button>
        `;
        
        tabsContainer.appendChild(tab);

        // Create editor content
        const editorContainer = document.querySelector('.editor-content');
        const editorDiv = document.createElement('div');
        editorDiv.className = 'editor-instance hidden';
        editorDiv.dataset.path = filePath;
        
        const textarea = document.createElement('textarea');
        textarea.value = this.extractContentFromHTML(content);
        editorDiv.appendChild(textarea);
        editorContainer.appendChild(editorDiv);

        // Initialize CodeMirror
        const editor = CodeMirror.fromTextArea(textarea, {
            lineNumbers: this.settings.lineNumbers,
            mode: this.detectLanguageMode(filePath),
            theme: this.settings.theme,
            indentUnit: this.settings.tabSize,
            lineWrapping: this.settings.wordWrap,
            matchBrackets: true,
            autoCloseBrackets: true,
            foldGutter: true,
            gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
            extraKeys: {
                "Ctrl-Space": "autocomplete",
                "Ctrl-/": "toggleComment"
            }
        });

        editor.on('change', () => {
            this.markFileAsUnsaved(filePath);
        });

        this.editors.set(filePath, editor);
    }

    extractContentFromHTML(html) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const textarea = doc.querySelector('#editor');
        return textarea ? textarea.value : '';
    }

    detectLanguageMode(filePath) {
        const ext = filePath.split('.').pop().toLowerCase();
        const modeMap = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'javascript',
            'json': 'application/json',
            'html': 'htmlmixed',
            'css': 'css',
            'scss': 'sass',
            'php': 'php',
            'java': 'text/x-java',
            'cpp': 'text/x-c++src',
            'c': 'text/x-csrc',
            'go': 'text/x-go',
            'rs': 'text/x-rustsrc',
            'yaml': 'yaml',
            'yml': 'yaml',
            'xml': 'xml',
            'md': 'markdown'
        };
        return modeMap[ext] || 'text/plain';
    }

    switchTab(filePath) {
        // Hide all editors and deactivate tabs
        document.querySelectorAll('.editor-instance').forEach(el => el.classList.add('hidden'));
        document.querySelectorAll('.editor-tab').forEach(el => el.classList.remove('active'));
        
        // Show active editor and tab
        const editorEl = document.querySelector(`[data-path="${filePath}"]`);
        const tabEl = document.querySelector(`.editor-tab[data-path="${filePath}"]`);
        
        if (editorEl && tabEl) {
            editorEl.classList.remove('hidden');
            tabEl.classList.add('active');
            this.activeTab = filePath;
            
            // Refresh CodeMirror
            const editor = this.editors.get(filePath);
            if (editor) {
                setTimeout(() => editor.refresh(), 10);
            }
            
            this.updateBreadcrumb(filePath);
        }
    }

    closeTab(filePath) {
        if (this.unsavedFiles.has(filePath)) {
            if (!confirm('You have unsaved changes. Are you sure you want to close this file?')) {
                return;
            }
        }

        // Remove tab and editor
        document.querySelector(`.editor-tab[data-path="${filePath}"]`)?.remove();
        document.querySelector(`.editor-instance[data-path="${filePath}"]`)?.remove();
        
        this.editors.delete(filePath);
        this.unsavedFiles.delete(filePath);
        
        // Switch to another tab if this was active
        if (this.activeTab === filePath) {
            const remainingTabs = document.querySelectorAll('.editor-tab');
            if (remainingTabs.length > 0) {
                this.switchTab(remainingTabs[0].dataset.path);
            } else {
                this.activeTab = null;
                this.showWelcomeScreen();
            }
        }
    }

    markFileAsUnsaved(filePath) {
        this.unsavedFiles.add(filePath);
        const tab = document.querySelector(`.editor-tab[data-path="${filePath}"]`);
        if (tab) {
            tab.querySelector('.tab-unsaved').classList.remove('hidden');
        }
    }

    markFileAsSaved(filePath) {
        this.unsavedFiles.delete(filePath);
        const tab = document.querySelector(`.editor-tab[data-path="${filePath}"]`);
        if (tab) {
            tab.querySelector('.tab-unsaved').classList.add('hidden');
        }
    }

    saveActiveFile() {
        if (!this.activeTab) return;
        
        const editor = this.editors.get(this.activeTab);
        if (!editor) return;

        const content = editor.getValue();
        const formData = new FormData();
        formData.append('content', content);
        formData.append('path', this.activeTab);

        fetch(`/bot/${window.botIndex}/save`, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.markFileAsSaved(this.activeTab);
                this.showToast('File saved successfully', 'success');
            } else {
                this.showToast('Error saving file: ' + data.message, 'error');
            }
        })
        .catch(error => {
            this.showToast('Failed to save file', 'error');
            console.error('Save error:', error);
        });
    }

    setupAutoSave() {
        let autoSaveTimeout;
        
        this.editors.forEach(editor => {
            editor.on('change', () => {
                if (autoSaveTimeout) clearTimeout(autoSaveTimeout);
                autoSaveTimeout = setTimeout(() => {
                    this.saveActiveFile();
                }, this.settings.autoSaveDelay);
            });
        });
    }

    showContextMenu(event, treeItem) {
        const contextMenu = document.getElementById('context-menu');
        const isFile = treeItem.classList.contains('tree-file');
        const filePath = treeItem.dataset.path;
        
        // Update context menu items based on file/folder
        const menuItems = contextMenu.querySelector('.context-menu-items');
        menuItems.innerHTML = `
            ${isFile ? '<li onclick="fileEditor.openFile(\'' + filePath + '\')"><i data-lucide="file-text"></i>Open</li>' : ''}
            <li onclick="fileEditor.showRenameDialog('${filePath}')"><i data-lucide="edit-2"></i>Rename</li>
            <li onclick="fileEditor.duplicateItem('${filePath}')"><i data-lucide="copy"></i>Duplicate</li>
            <li onclick="fileEditor.downloadItem('${filePath}')"><i data-lucide="download"></i>Download</li>
            <li class="separator"></li>
            <li onclick="fileEditor.showCreateModal('file', '${filePath}')" class="create-action"><i data-lucide="file-plus"></i>New File</li>
            <li onclick="fileEditor.showCreateModal('folder', '${filePath}')" class="create-action"><i data-lucide="folder-plus"></i>New Folder</li>
            <li class="separator"></li>
            <li onclick="fileEditor.deleteItem('${filePath}')" class="danger-action"><i data-lucide="trash-2"></i>Delete</li>
        `;
        
        // Position and show menu
        contextMenu.style.left = `${event.pageX}px`;
        contextMenu.style.top = `${event.pageY}px`;
        contextMenu.classList.remove('hidden');
        
        // Re-initialize Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }
        
        // Hide on click outside
        setTimeout(() => {
            document.addEventListener('click', this.hideContextMenu, { once: true });
        }, 10);
    }

    hideContextMenu() {
        document.getElementById('context-menu').classList.add('hidden');
    }

    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container');
        const toast = document.createElement('div');
        
        const typeClasses = {
            success: 'bg-green-500/90 border-green-400',
            error: 'bg-red-500/90 border-red-400',
            warning: 'bg-yellow-500/90 border-yellow-400',
            info: 'bg-blue-500/90 border-blue-400'
        };
        
        toast.className = `toast-message px-4 py-3 rounded-lg shadow-lg text-white border backdrop-blur-sm ${typeClasses[type]} transform translate-x-full transition-transform duration-300`;
        toast.textContent = message;
        
        toastContainer.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.classList.remove('translate-x-full');
        }, 10);
        
        // Auto remove
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    showLoadingIndicator() {
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.classList.remove('hidden');
        }
    }

    hideLoadingIndicator() {
        const indicator = document.getElementById('loading-indicator');
        if (indicator) {
            indicator.classList.add('hidden');
        }
    }

    updateBreadcrumb(filePath) {
        const breadcrumb = document.querySelector('.breadcrumb');
        if (!breadcrumb) return;
        
        const parts = filePath.split('/').filter(part => part);
        const breadcrumbHTML = parts.map((part, index) => {
            const path = parts.slice(0, index + 1).join('/');
            return `<span class="breadcrumb-item" data-path="${path}">${part}</span>`;
        }).join('<span class="breadcrumb-separator">/</span>');
        
        breadcrumb.innerHTML = `<span class="breadcrumb-root">~</span><span class="breadcrumb-separator">/</span>${breadcrumbHTML}`;
    }

    showWelcomeScreen() {
        const editorContent = document.querySelector('.editor-content');
        editorContent.innerHTML = `
            <div class="welcome-screen">
                <div class="welcome-content">
                    <i data-lucide="code-2" class="welcome-icon"></i>
                    <h2>Welcome to the File Editor</h2>
                    <p>Select a file from the sidebar to start editing, or create a new file.</p>
                    <div class="welcome-actions">
                        <button onclick="fileEditor.showCreateModal('file')" class="btn btn-primary">
                            <i data-lucide="file-plus"></i>
                            New File
                        </button>
                        <button onclick="fileEditor.showCreateModal('folder')" class="btn btn-secondary">
                            <i data-lucide="folder-plus"></i>
                            New Folder
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        if (window.lucide) {
            lucide.createIcons();
        }
    }

    toggleFolder(folderItem) {
        folderItem.classList.toggle('open');
        const nestedTree = folderItem.querySelector('.nested-tree');
        if (nestedTree) {
            if (folderItem.classList.contains('open')) {
                nestedTree.style.maxHeight = nestedTree.scrollHeight + 'px';
            } else {
                nestedTree.style.maxHeight = '0';
            }
        }
    }

    showSettingsModal() {
        const modal = document.getElementById('settings-modal');
        if (modal) {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        }
    }

    hideSettingsModal() {
        const modal = document.getElementById('settings-modal');
        if (modal) {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }
    }

    updateSetting(key, value) {
        this.settings[key] = value;
        this.saveSettings();
        this.applySettings();
        
        if (key === 'theme') {
            this.setupTheme();
        }
    }

    showSearchDialog() {
        if (!this.activeTab) return;
        
        const editor = this.editors.get(this.activeTab);
        if (editor) {
            editor.execCommand('find');
        }
    }

    switchToPreviousTab() {
        const tabs = Array.from(document.querySelectorAll('.editor-tab'));
        const currentIndex = tabs.findIndex(tab => tab.dataset.path === this.activeTab);
        if (currentIndex > 0) {
            this.switchTab(tabs[currentIndex - 1].dataset.path);
        }
    }

    switchToNextTab() {
        const tabs = Array.from(document.querySelectorAll('.editor-tab'));
        const currentIndex = tabs.findIndex(tab => tab.dataset.path === this.activeTab);
        if (currentIndex < tabs.length - 1) {
            this.switchTab(tabs[currentIndex + 1].dataset.path);
        }
    }

    toggleSidebar() {
        const sidebar = document.getElementById('editor-sidebar');
        const backdrop = document.querySelector('.sidebar-backdrop');
        
        this.sidebarOpen = !this.sidebarOpen;
        
        if (window.innerWidth <= 768) {
            // Mobile behavior
            if (this.sidebarOpen) {
                sidebar.classList.add('mobile-open');
                if (!backdrop) {
                    const newBackdrop = document.createElement('div');
                    newBackdrop.className = 'sidebar-backdrop';
                    newBackdrop.onclick = () => this.toggleSidebar();
                    document.body.appendChild(newBackdrop);
                    setTimeout(() => newBackdrop.classList.add('active'), 10);
                } else {
                    backdrop.classList.add('active');
                }
            } else {
                sidebar.classList.remove('mobile-open');
                if (backdrop) {
                    backdrop.classList.remove('active');
                    setTimeout(() => backdrop.remove(), 300);
                }
            }
        } else {
            // Desktop behavior
            sidebar.classList.toggle('collapsed');
        }
    }

    showCreateModal(type, basePath = '') {
        const modal = document.getElementById('create-modal');
        const title = document.getElementById('modal-title');
        const typeInput = document.getElementById('modal-item-type');
        const pathInput = document.getElementById('modal-base-path');
        const nameInput = document.getElementById('modal-item-name');
        
        title.textContent = `Create New ${type.charAt(0).toUpperCase() + type.slice(1)}`;
        typeInput.value = type;
        pathInput.value = basePath;
        nameInput.value = '';
        
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        nameInput.focus();
    }

    hideCreateModal() {
        const modal = document.getElementById('create-modal');
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }

    async handleCreateSubmit(event) {
        event.preventDefault();
        
        const formData = new FormData(event.target);
        
        try {
            const response = await fetch(`/bot/${window.botIndex}/create`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showToast(result.message, 'success');
                this.hideCreateModal();
                // Refresh file tree
                setTimeout(() => window.location.reload(), 500);
            } else {
                this.showToast(result.message, 'error');
            }
        } catch (error) {
            this.showToast('Failed to create item', 'error');
        }
    }

    refreshFileTree() {
        window.location.reload();
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.fileEditor = new ModernFileEditor();
    
    // Initialize file operations
    if (typeof FileOperations !== 'undefined') {
        window.fileOperations = new FileOperations(window.fileEditor);
    }
    
    // Setup mobile-specific features
    if (window.innerWidth <= 768) {
        document.body.classList.add('mobile-view');
        
        // Add mobile navigation functionality
        const mobileNavItems = document.querySelectorAll('.mobile-nav-item');
        mobileNavItems.forEach(item => {
            item.addEventListener('click', () => {
                mobileNavItems.forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
            });
        });
    }
    
    // Handle window resize
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768 && window.fileEditor.sidebarOpen) {
            const sidebar = document.getElementById('editor-sidebar');
            const backdrop = document.querySelector('.sidebar-backdrop');
            
            sidebar.classList.remove('mobile-open');
            if (backdrop) {
                backdrop.remove();
            }
        }
        
        // Refresh all editors on resize
        window.fileEditor.editors.forEach(editor => {
            setTimeout(() => editor.refresh(), 100);
        });
    });
});