/**
 * Application Initialization
 * Main entry point that orchestrates the entire application
 */

(async function initializeApp() {
    console.log('🚀 Initializing Codebase Manager Dashboard...');
    
    try {
        // 1. Load layout components
        console.log('📦 Loading layout components...');
        await componentLoader.loadComponents([
            { name: 'layout/sidebar', container: '#sidebar-container' },
            { name: 'layout/header', container: '#header-container' }
        ]);
        
        // 2. Load modals
        console.log('📦 Loading modals...');
        await componentLoader.loadComponent('modals/tool_history', '#modals-container');
        
        // 3. Check API connection
        console.log('🔌 Checking API connection...');
        const healthResult = await apiRoutes.health.check();
        
        if (healthResult.success) {
            notifications.success('Connected to API server');
            appState.set('connected', true);
            
            // Update connection status in header
            await updateConnectionStatus();
        } else {
            notifications.error('Failed to connect to API server');
            appState.set('connected', false);
        }
        
        // 4. Load initial working directory info
        console.log('📁 Loading working directory info...');
        const dirResult = await apiRoutes.workingDirectory.get();
        
        if (dirResult.success && dirResult.data.result) {
            const workingDir = dirResult.data.result.working_directory;
            appState.set('workingDirectory', workingDir);
            
            // Update sidebar status
            const dirElement = document.getElementById('dirStatus');
            if (dirElement) {
                dirElement.textContent = workingDir.split(/[\\/]/).pop() || workingDir;
                dirElement.title = workingDir;
            }
        }
        
        // 5. Load current git session
        console.log('🌿 Loading git session info...');
        const sessionResult = await apiRoutes.session.current();
        
        if (sessionResult.success && sessionResult.data.result) {
            appState.update({
                'currentBranch': sessionResult.data.result.current_branch,
                'isSessionBranch': sessionResult.data.result.is_session_branch
            });
        }
        
        // 6. Load initial section from URL hash or default to dashboard
        const initialSection = window.location.hash.slice(1) || 'dashboard';
        console.log(`📄 Loading initial section: ${initialSection}`);
        await router.loadSection(initialSection);
        
        // 7. Set up global event listeners
        setupGlobalEventListeners();
        
        // 8. Set up auto-refresh if enabled
        setupAutoRefresh();
        
        // 9. Initialize keyboard shortcuts
        setupKeyboardShortcuts();
        
        console.log('✅ Application initialized successfully!');
        
        // Show welcome notification
        setTimeout(() => {
            notifications.info('Dashboard ready! Press Ctrl+H for tool history', 4000);
        }, 1000);
        
    } catch (error) {
        console.error('❌ Failed to initialize application:', error);
        notifications.error('Failed to initialize dashboard: ' + error.message);
    }
})();

/**
 * Setup global event listeners
 */
function setupGlobalEventListeners() {
    // Tool logger events
    toolLogger.subscribe((entry) => {
        // Update tool call count in sidebar
        const countElement = document.getElementById('toolCallCount');
        if (countElement) {
            const stats = toolLogger.getStats();
            countElement.textContent = stats.totalCalls;
        }
        
        // Show notification for errors
        if (entry.status === 'error') {
            notifications.error(`API Error: ${entry.route}`, 5000);
        }
    });
    
    // State changes
    appState.subscribe('connected', (connected) => {
        const indicator = document.getElementById('connectionIndicator');
        const text = document.getElementById('connectionText');
        
        if (indicator && text) {
            if (connected) {
                indicator.innerHTML = `
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                `;
                text.textContent = 'Connected';
                text.className = 'text-green-600 font-medium hidden sm:inline';
            } else {
                indicator.innerHTML = `
                    <span class="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                `;
                text.textContent = 'Disconnected';
                text.className = 'text-red-600 font-medium hidden sm:inline';
            }
        }
    });
    
    // Window resize handling
    window.addEventListener('resize', () => {
        if (window.innerWidth >= 1024) {
            // Close mobile overlay on desktop
            closeSidebar();
        }
    });
}

/**
 * Setup auto-refresh functionality
 */
function setupAutoRefresh() {
    const preferences = appState.get('preferences');
    
    if (preferences.autoRefresh) {
        const interval = preferences.refreshInterval || 30000;
        
        setInterval(() => {
            const currentSection = appState.get('currentSection');
            const refreshFunction = window[`refresh${capitalize(currentSection)}`];
            
            if (typeof refreshFunction === 'function') {
                refreshFunction();
            }
        }, interval);
    }
}

/**
 * Setup keyboard shortcuts
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + H = Tool History
        if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
            e.preventDefault();
            showToolHistory();
        }
        
        // Ctrl/Cmd + R = Refresh
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            refreshAll();
        }
        
        // Ctrl/Cmd + K = Quick search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            loadSection('search');
            setTimeout(() => {
                document.getElementById('searchQuery')?.focus();
            }, 300);
        }
        
        // Escape = Close modals/sidebar
        if (e.key === 'Escape') {
            closeToolHistory();
            closeSidebar();
        }
        
        // Number keys for quick navigation (1-9)
        if (e.altKey && e.key >= '1' && e.key <= '9') {
            e.preventDefault();
            const sections = ['dashboard', 'search', 'files', 'git', 'memory', 'project', 'directory', 'working-directory', 'logs'];
            const index = parseInt(e.key) - 1;
            if (sections[index]) {
                loadSection(sections[index]);
            }
        }
    });
    
    console.log('⌨️  Keyboard shortcuts enabled');
}

/**
 * Utility function
 */
function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1).replace(/-([a-z])/g, (g) => g[1].toUpperCase());
}

// Export for debugging
window.appDebug = {
    state: () => appState.state,
    toolLogger: () => toolLogger.getStats(),
    clearAll: () => {
        if (confirm('Clear ALL data including tool history and logs?')) {
            toolLogger.clear();
            localStorage.clear();
            location.reload();
        }
    }
};

console.log('💡 Debug utilities available via window.appDebug');
console.log('⌨️  Keyboard shortcuts:');
console.log('  Ctrl+H: Tool History');
console.log('  Ctrl+R: Refresh');
console.log('  Ctrl+K: Quick Search');
console.log('  Alt+1-9: Quick Navigation');
console.log('  Esc: Close Modals');
