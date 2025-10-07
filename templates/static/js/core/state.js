/**
 * Global State Management
 * Manages application state with reactive updates
 */

class StateManager {
    constructor() {
        this.state = {
            // System state
            connected: false,
            loading: false,
            workingDirectory: null,
            
            // Services status
            services: {
                searchEngine: false,
                writePipeline: false,
                editPipeline: false,
                memoryManager: false,
                gitManager: false,
                projectManager: false,
                directoryLister: false
            },
            
            // Current view
            currentSection: 'dashboard',
            
            // User preferences
            preferences: this.loadPreferences(),
            
            // Session info
            currentBranch: null,
            isSessionBranch: false,
            
            // Statistics
            stats: {
                projectFiles: 0,
                totalSize: '0B',
                codeLines: 0,
                totalMemories: 0
            }
        };
        
        this.listeners = {};
    }
    
    /**
     * Get state value
     */
    get(key) {
        return this.getNestedValue(this.state, key);
    }
    
    /**
     * Set state value and notify listeners
     */
    set(key, value) {
        this.setNestedValue(this.state, key, value);
        this.notify(key, value);
    }
    
    /**
     * Update multiple state values
     */
    update(updates) {
        Object.keys(updates).forEach(key => {
            this.set(key, updates[key]);
        });
    }
    
    /**
     * Subscribe to state changes
     */
    subscribe(key, callback) {
        if (!this.listeners[key]) {
            this.listeners[key] = [];
        }
        this.listeners[key].push(callback);
        
        // Return unsubscribe function
        return () => {
            this.listeners[key] = this.listeners[key].filter(cb => cb !== callback);
        };
    }
    
    /**
     * Notify listeners of state change
     */
    notify(key, value) {
        if (this.listeners[key]) {
            this.listeners[key].forEach(callback => {
                try {
                    callback(value);
                } catch (e) {
                    console.error('State listener error:', e);
                }
            });
        }
        
        // Also notify wildcard listeners
        if (this.listeners['*']) {
            this.listeners['*'].forEach(callback => {
                try {
                    callback(key, value);
                } catch (e) {
                    console.error('Wildcard listener error:', e);
                }
            });
        }
    }
    
    /**
     * Get nested value from object using dot notation
     */
    getNestedValue(obj, path) {
        return path.split('.').reduce((acc, part) => acc && acc[part], obj);
    }
    
    /**
     * Set nested value in object using dot notation
     */
    setNestedValue(obj, path, value) {
        const parts = path.split('.');
        const last = parts.pop();
        const target = parts.reduce((acc, part) => {
            if (!acc[part]) acc[part] = {};
            return acc[part];
        }, obj);
        target[last] = value;
    }
    
    /**
     * Load preferences from localStorage
     */
    loadPreferences() {
        try {
            const stored = localStorage.getItem('dashboardPreferences');
            return stored ? JSON.parse(stored) : {
                autoRefresh: false,
                refreshInterval: 30000,
                compactMode: false,
                showTimestamps: true,
                theme: 'light',
                sidebarCollapsed: false
            };
        } catch (e) {
            console.error('Failed to load preferences:', e);
            return {};
        }
    }
    
    /**
     * Save preferences to localStorage
     */
    savePreferences() {
        try {
            localStorage.setItem('dashboardPreferences', JSON.stringify(this.state.preferences));
        } catch (e) {
            console.error('Failed to save preferences:', e);
        }
    }
    
    /**
     * Reset state to defaults
     */
    reset() {
        this.state = {
            connected: false,
            loading: false,
            workingDirectory: null,
            services: {},
            currentSection: 'dashboard',
            preferences: this.loadPreferences(),
            currentBranch: null,
            isSessionBranch: false,
            stats: {}
        };
        this.notify('*', this.state);
    }
}

// Global instance
window.appState = new StateManager();

console.log('🔧 State Manager initialized');
