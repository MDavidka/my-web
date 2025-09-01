// File Operations Module
class FileOperations {
    constructor(editor) {
        this.editor = editor;
        this.setupDragAndDrop();
    }

    setupDragAndDrop() {
        const sidebar = document.querySelector('.file-tree-container');
        
        // File upload via drag and drop
        sidebar.addEventListener('dragover', (e) => {
            e.preventDefault();
            sidebar.classList.add('drag-over');
        });
        
        sidebar.addEventListener('dragleave', (e) => {
            if (!sidebar.contains(e.relatedTarget)) {
                sidebar.classList.remove('drag-over');
            }
        });
        
        sidebar.addEventListener('drop', (e) => {
            e.preventDefault();
            sidebar.classList.remove('drag-over');
            
            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                this.uploadFiles(files);
            }
        });
    }

    async uploadFiles(files) {
        const uploadPromises = files.map(file => this.uploadSingleFile(file));
        
        try {
            await Promise.all(uploadPromises);
            this.editor.showToast(`Successfully uploaded ${files.length} file(s)`, 'success');
            this.refreshFileTree();
        } catch (error) {
            this.editor.showToast('Some files failed to upload', 'error');
        }
    }

    async uploadSingleFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('path', ''); // Upload to root for now
        
        const response = await fetch(`/bot/${window.botIndex}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Failed to upload ${file.name}`);
        }
        
        return response.json();
    }

    async downloadItem(filePath) {
        try {
            const response = await fetch(`/bot/${window.botIndex}/download?path=${encodeURIComponent(filePath)}`);
            
            if (!response.ok) {
                throw new Error('Download failed');
            }
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filePath.split('/').pop();
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.editor.showToast('Download started', 'success');
        } catch (error) {
            this.editor.showToast('Download failed', 'error');
        }
    }

    async duplicateItem(filePath) {
        const fileName = filePath.split('/').pop();
        const baseName = fileName.split('.')[0];
        const extension = fileName.includes('.') ? '.' + fileName.split('.').pop() : '';
        const newName = `${baseName}_copy${extension}`;
        
        try {
            const response = await fetch(`/bot/${window.botIndex}/duplicate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_path: filePath,
                    new_name: newName
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.editor.showToast('Item duplicated successfully', 'success');
                this.refreshFileTree();
            } else {
                this.editor.showToast('Failed to duplicate item', 'error');
            }
        } catch (error) {
            this.editor.showToast('Duplication failed', 'error');
        }
    }

    async deleteItem(filePath) {
        const fileName = filePath.split('/').pop();
        
        if (!confirm(`Are you sure you want to delete "${fileName}"? This action cannot be undone.`)) {
            return;
        }
        
        try {
            const formData = new FormData();
            formData.append('path', filePath);
            
            const response = await fetch(`/bot/${window.botIndex}/delete`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.editor.showToast('Item deleted successfully', 'success');
                
                // Close tab if file was open
                if (this.editor.editors.has(filePath)) {
                    this.editor.closeTab(filePath);
                }
                
                this.refreshFileTree();
            } else {
                this.editor.showToast('Failed to delete item', 'error');
            }
        } catch (error) {
            this.editor.showToast('Deletion failed', 'error');
        }
    }

    showRenameDialog(filePath) {
        const currentName = filePath.split('/').pop();
        const newName = prompt('Enter new name:', currentName);
        
        if (newName && newName !== currentName) {
            this.renameItem(filePath, newName);
        }
    }

    async renameItem(filePath, newName) {
        try {
            const formData = new FormData();
            formData.append('path', filePath);
            formData.append('new_name', newName);
            
            const response = await fetch(`/bot/${window.botIndex}/rename`, {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.editor.showToast('Item renamed successfully', 'success');
                
                // Update tab if file was open
                const oldPath = filePath;
                const newPath = filePath.replace(/[^/]+$/, newName);
                
                if (this.editor.editors.has(oldPath)) {
                    const editor = this.editor.editors.get(oldPath);
                    this.editor.editors.delete(oldPath);
                    this.editor.editors.set(newPath, editor);
                    
                    // Update tab
                    const tab = document.querySelector(`[data-path="${oldPath}"]`);
                    if (tab) {
                        tab.dataset.path = newPath;
                        tab.querySelector('.tab-name').textContent = newName;
                    }
                    
                    if (this.editor.activeTab === oldPath) {
                        this.editor.activeTab = newPath;
                    }
                }
                
                this.refreshFileTree();
            } else {
                this.editor.showToast('Failed to rename item', 'error');
            }
        } catch (error) {
            this.editor.showToast('Rename failed', 'error');
        }
    }

    refreshFileTree() {
        // Reload the page to refresh the file tree
        // In a real implementation, this would be an AJAX call
        window.location.reload();
    }

    async createArchive(filePaths) {
        try {
            const response = await fetch(`/bot/${window.botIndex}/archive`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paths: filePaths })
            });
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'archive.zip';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.editor.showToast('Archive created and downloaded', 'success');
            } else {
                throw new Error('Archive creation failed');
            }
        } catch (error) {
            this.editor.showToast('Failed to create archive', 'error');
        }
    }

    async extractArchive(archivePath) {
        try {
            const response = await fetch(`/bot/${window.botIndex}/extract`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ archive_path: archivePath })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.editor.showToast('Archive extracted successfully', 'success');
                this.refreshFileTree();
            } else {
                this.editor.showToast('Failed to extract archive', 'error');
            }
        } catch (error) {
            this.editor.showToast('Extraction failed', 'error');
        }
    }
}

// Search functionality
class EditorSearch {
    constructor(editor) {
        this.editor = editor;
        this.searchResults = [];
        this.currentResultIndex = 0;
    }

    async searchInFiles(query, options = {}) {
        const { caseSensitive = false, regex = false, filePattern = '*' } = options;
        
        try {
            const response = await fetch(`/bot/${window.botIndex}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    case_sensitive: caseSensitive,
                    regex,
                    file_pattern: filePattern
                })
            });
            
            const results = await response.json();
            this.displaySearchResults(results);
        } catch (error) {
            this.editor.showToast('Search failed', 'error');
        }
    }

    displaySearchResults(results) {
        // Implementation for displaying search results in a panel
        console.log('Search results:', results);
    }
}

// File history and versioning
class FileHistory {
    constructor(editor) {
        this.editor = editor;
        this.history = new Map();
    }

    saveVersion(filePath, content) {
        if (!this.history.has(filePath)) {
            this.history.set(filePath, []);
        }
        
        const versions = this.history.get(filePath);
        versions.push({
            content,
            timestamp: new Date(),
            id: Date.now()
        });
        
        // Keep only last 10 versions
        if (versions.length > 10) {
            versions.shift();
        }
    }

    getVersions(filePath) {
        return this.history.get(filePath) || [];
    }

    restoreVersion(filePath, versionId) {
        const versions = this.getVersions(filePath);
        const version = versions.find(v => v.id === versionId);
        
        if (version && this.editor.editors.has(filePath)) {
            const editor = this.editor.editors.get(filePath);
            editor.setValue(version.content);
            this.editor.showToast('Version restored', 'success');
        }
    }
}