// Editor Extensions and Advanced Features

class EditorExtensions {
    constructor(editor) {
        this.editor = editor;
        this.minimap = null;
        this.linter = null;
        this.autocomplete = null;
        
        this.init();
    }

    init() {
        this.setupMinimap();
        this.setupLinting();
        this.setupAutocomplete();
        this.setupFilePreview();
    }

    setupMinimap() {
        // Minimap implementation (simplified)
        this.minimap = {
            enabled: false,
            toggle: () => {
                this.minimap.enabled = !this.minimap.enabled;
                this.updateMinimapVisibility();
            }
        };
    }

    updateMinimapVisibility() {
        const minimapContainer = document.querySelector('.minimap-container');
        if (this.minimap.enabled && minimapContainer) {
            minimapContainer.classList.remove('hidden');
        } else if (minimapContainer) {
            minimapContainer.classList.add('hidden');
        }
    }

    setupLinting() {
        this.linter = {
            enabled: true,
            lint: (editor, content, mode) => {
                // Basic linting for common issues
                const lines = content.split('\n');
                const markers = [];
                
                lines.forEach((line, index) => {
                    // Check for common issues
                    if (mode === 'python') {
                        // Check for missing imports
                        if (line.includes('discord.') && !content.includes('import discord')) {
                            markers.push({
                                from: { line: index, ch: 0 },
                                to: { line: index, ch: line.length },
                                message: 'Missing import: discord',
                                severity: 'warning'
                            });
                        }
                    }
                    
                    if (mode === 'javascript') {
                        // Check for console.log statements
                        if (line.includes('console.log')) {
                            markers.push({
                                from: { line: index, ch: line.indexOf('console.log') },
                                to: { line: index, ch: line.indexOf('console.log') + 11 },
                                message: 'Consider removing console.log in production',
                                severity: 'info'
                            });
                        }
                    }
                });
                
                return markers;
            }
        };
    }

    setupAutocomplete() {
        this.autocomplete = {
            getCompletions: (editor, mode) => {
                const completions = {
                    python: [
                        'import discord',
                        'from discord.ext import commands',
                        'async def',
                        'await',
                        'print(',
                        'if __name__ == "__main__":',
                        'try:',
                        'except Exception as e:',
                        'class',
                        'def'
                    ],
                    javascript: [
                        'console.log(',
                        'function',
                        'const',
                        'let',
                        'var',
                        'if (',
                        'for (',
                        'while (',
                        'try {',
                        'catch (error) {'
                    ]
                };
                
                return completions[mode] || [];
            }
        };
    }

    setupFilePreview() {
        this.preview = {
            canPreview: (filePath) => {
                const ext = filePath.split('.').pop().toLowerCase();
                return ['md', 'json', 'txt', 'log'].includes(ext);
            },
            
            generatePreview: (filePath, content) => {
                const ext = filePath.split('.').pop().toLowerCase();
                
                switch (ext) {
                    case 'md':
                        return this.renderMarkdown(content);
                    case 'json':
                        return this.renderJSON(content);
                    case 'log':
                        return this.renderLog(content);
                    default:
                        return `<pre>${content}</pre>`;
                }
            }
        };
    }

    renderMarkdown(content) {
        // Simple markdown rendering (in a real app, use a proper markdown parser)
        return content
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*)\*/gim, '<em>$1</em>')
            .replace(/`(.*)`/gim, '<code>$1</code>')
            .replace(/\n/gim, '<br>');
    }

    renderJSON(content) {
        try {
            const parsed = JSON.parse(content);
            return `<pre>${JSON.stringify(parsed, null, 2)}</pre>`;
        } catch (e) {
            return `<pre class="error">Invalid JSON: ${e.message}</pre>`;
        }
    }

    renderLog(content) {
        const lines = content.split('\n');
        const coloredLines = lines.map(line => {
            if (line.includes('ERROR') || line.includes('FATAL')) {
                return `<span class="log-error">${line}</span>`;
            } else if (line.includes('WARNING') || line.includes('WARN')) {
                return `<span class="log-warning">${line}</span>`;
            } else if (line.includes('INFO')) {
                return `<span class="log-info">${line}</span>`;
            }
            return line;
        });
        
        return `<pre class="log-content">${coloredLines.join('\n')}</pre>`;
    }
}

// Terminal Integration
class IntegratedTerminal {
    constructor(editor) {
        this.editor = editor;
        this.isVisible = false;
        this.history = [];
        this.historyIndex = 0;
        
        this.init();
    }

    init() {
        this.createTerminalUI();
        this.setupEventListeners();
    }

    createTerminalUI() {
        const terminalHTML = `
            <div id="integrated-terminal" class="integrated-terminal hidden">
                <div class="terminal-header">
                    <div class="terminal-tabs">
                        <div class="terminal-tab active">
                            <span>Terminal</span>
                            <button onclick="terminal.close()" class="terminal-tab-close">×</button>
                        </div>
                    </div>
                    <div class="terminal-actions">
                        <button onclick="terminal.clear()" class="btn-icon" title="Clear">
                            <i data-lucide="trash-2"></i>
                        </button>
                        <button onclick="terminal.toggle()" class="btn-icon" title="Close">
                            <i data-lucide="x"></i>
                        </button>
                    </div>
                </div>
                <div class="terminal-content">
                    <div class="terminal-output" id="terminal-output"></div>
                    <div class="terminal-input-line">
                        <span class="terminal-prompt">$</span>
                        <input type="text" class="terminal-input" id="terminal-input" 
                               placeholder="Type a command..." autocomplete="off">
                    </div>
                </div>
            </div>
        `;
        
        document.querySelector('.editor-main').insertAdjacentHTML('beforeend', terminalHTML);
    }

    setupEventListeners() {
        const input = document.getElementById('terminal-input');
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                this.executeCommand(input.value);
                input.value = '';
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.navigateHistory(-1);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.navigateHistory(1);
            }
        });
    }

    toggle() {
        const terminal = document.getElementById('integrated-terminal');
        this.isVisible = !this.isVisible;
        
        if (this.isVisible) {
            terminal.classList.remove('hidden');
            document.getElementById('terminal-input').focus();
        } else {
            terminal.classList.add('hidden');
        }
    }

    async executeCommand(command) {
        if (!command.trim()) return;
        
        this.history.push(command);
        this.historyIndex = this.history.length;
        
        this.addOutput(`$ ${command}`, 'command');
        
        try {
            const response = await fetch(`/bot/${window.botIndex}/terminal`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.addOutput(result.output, 'output');
            } else {
                this.addOutput(result.error, 'error');
            }
        } catch (error) {
            this.addOutput(`Error: ${error.message}`, 'error');
        }
    }

    addOutput(text, type = 'output') {
        const output = document.getElementById('terminal-output');
        const line = document.createElement('div');
        line.className = `terminal-line terminal-${type}`;
        line.textContent = text;
        output.appendChild(line);
        output.scrollTop = output.scrollHeight;
    }

    clear() {
        document.getElementById('terminal-output').innerHTML = '';
    }

    close() {
        this.isVisible = false;
        document.getElementById('integrated-terminal').classList.add('hidden');
    }

    navigateHistory(direction) {
        const input = document.getElementById('terminal-input');
        
        if (direction === -1 && this.historyIndex > 0) {
            this.historyIndex--;
            input.value = this.history[this.historyIndex];
        } else if (direction === 1 && this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            input.value = this.history[this.historyIndex];
        } else if (direction === 1 && this.historyIndex === this.history.length - 1) {
            this.historyIndex = this.history.length;
            input.value = '';
        }
    }
}

// Initialize extensions
document.addEventListener('DOMContentLoaded', () => {
    if (window.fileEditor) {
        window.editorExtensions = new EditorExtensions(window.fileEditor);
        window.terminal = new IntegratedTerminal(window.fileEditor);
        window.fileOperations = new FileOperations(window.fileEditor);
    }
});