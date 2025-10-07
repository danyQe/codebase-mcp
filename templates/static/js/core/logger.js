/**
 * Tool Call Logger - Records all API interactions for analysis and improvement
 * CRITICAL: This helps identify patterns, errors, and optimization opportunities
 */

class ToolCallLogger {
    constructor() {
        this.history = this.loadHistory();
        this.maxHistory = 1000;
        this.listeners = [];
        
        // Statistics
        this.stats = {
            totalCalls: 0,
            successCount: 0,
            errorCount: 0,
            totalDuration: 0,
            routeStats: {}
        };
        
        this.calculateStats();
    }
    
    /**
     * Log a tool call with full details
     */
    log(call) {
        const logEntry = {
            id: Date.now() + Math.random(), // Unique ID
            timestamp: new Date().toISOString(),
            route: call.route,
            method: call.method,
            request: this.sanitize(call.request),
            response: this.sanitize(call.response),
            duration: call.duration,
            status: call.status,
            statusCode: call.statusCode,
            error: call.error,
            userAction: call.userAction || 'Unknown',
            context: call.context || {}
        };
        
        // Add to history
        this.history.unshift(logEntry);
        
        // Maintain max history
        if (this.history.length > this.maxHistory) {
            this.history = this.history.slice(0, this.maxHistory);
        }
        
        // Update stats
        this.updateStats(logEntry);
        
        // Persist
        this.persist();
        
        // Notify listeners
        this.notifyListeners(logEntry);
        
        return logEntry;
    }
    
    /**
     * Sanitize sensitive data
     */
    sanitize(data) {
        if (!data) return data;
        
        const sanitized = JSON.parse(JSON.stringify(data));
        
        // Remove sensitive keys
        const sensitiveKeys = ['password', 'token', 'api_key', 'secret'];
        const sanitizeObj = (obj) => {
            if (typeof obj !== 'object' || obj === null) return;
            
            for (let key in obj) {
                if (sensitiveKeys.some(k => key.toLowerCase().includes(k))) {
                    obj[key] = '***REDACTED***';
                } else if (typeof obj[key] === 'object') {
                    sanitizeObj(obj[key]);
                }
            }
        };
        
        sanitizeObj(sanitized);
        return sanitized;
    }
    
    /**
     * Update statistics
     */
    updateStats(entry) {
        this.stats.totalCalls++;
        this.stats.totalDuration += entry.duration || 0;
        
        if (entry.status === 'success') {
            this.stats.successCount++;
        } else if (entry.status === 'error') {
            this.stats.errorCount++;
        }
        
        // Route-specific stats
        if (!this.stats.routeStats[entry.route]) {
            this.stats.routeStats[entry.route] = {
                count: 0,
                errors: 0,
                totalDuration: 0,
                avgDuration: 0
            };
        }
        
        const routeStat = this.stats.routeStats[entry.route];
        routeStat.count++;
        routeStat.totalDuration += entry.duration || 0;
        routeStat.avgDuration = routeStat.totalDuration / routeStat.count;
        
        if (entry.status === 'error') {
            routeStat.errors++;
        }
    }
    
    /**
     * Recalculate all statistics
     */
    calculateStats() {
        this.stats = {
            totalCalls: 0,
            successCount: 0,
            errorCount: 0,
            totalDuration: 0,
            routeStats: {}
        };
        
        this.history.forEach(entry => {
            this.updateStats(entry);
        });
    }
    
    /**
     * Get statistics
     */
    getStats() {
        return {
            ...this.stats,
            avgDuration: this.stats.totalCalls > 0 
                ? this.stats.totalDuration / this.stats.totalCalls 
                : 0,
            successRate: this.stats.totalCalls > 0
                ? (this.stats.successCount / this.stats.totalCalls * 100).toFixed(2)
                : 0,
            errorRate: this.stats.totalCalls > 0
                ? (this.stats.errorCount / this.stats.totalCalls * 100).toFixed(2)
                : 0
        };
    }
    
    /**
     * Get filtered history
     */
    getHistory(filters = {}) {
        let filtered = [...this.history];
        
        if (filters.route) {
            filtered = filtered.filter(e => e.route === filters.route);
        }
        
        if (filters.status) {
            filtered = filtered.filter(e => e.status === filters.status);
        }
        
        if (filters.method) {
            filtered = filtered.filter(e => e.method === filters.method);
        }
        
        if (filters.startDate) {
            filtered = filtered.filter(e => new Date(e.timestamp) >= new Date(filters.startDate));
        }
        
        if (filters.endDate) {
            filtered = filtered.filter(e => new Date(e.timestamp) <= new Date(filters.endDate));
        }
        
        if (filters.search) {
            const searchLower = filters.search.toLowerCase();
            filtered = filtered.filter(e => 
                e.route.toLowerCase().includes(searchLower) ||
                e.userAction.toLowerCase().includes(searchLower) ||
                JSON.stringify(e.request).toLowerCase().includes(searchLower) ||
                JSON.stringify(e.response).toLowerCase().includes(searchLower)
            );
        }
        
        return filtered;
    }
    
    /**
     * Export history to JSON
     */
    export(filters = {}) {
        const data = {
            exportDate: new Date().toISOString(),
            stats: this.getStats(),
            history: this.getHistory(filters)
        };
        
        return JSON.stringify(data, null, 2);
    }
    
    /**
     * Export as CSV
     */
    exportCSV(filters = {}) {
        const history = this.getHistory(filters);
        const headers = ['Timestamp', 'Route', 'Method', 'Status', 'Duration', 'User Action'];
        
        let csv = headers.join(',') + '\n';
        
        history.forEach(entry => {
            const row = [
                entry.timestamp,
                entry.route,
                entry.method,
                entry.status,
                entry.duration || 0,
                entry.userAction
            ].map(v => `"${v}"`).join(',');
            
            csv += row + '\n';
        });
        
        return csv;
    }
    
    /**
     * Clear history
     */
    clear() {
        if (confirm('Are you sure you want to clear all tool call history? This cannot be undone.')) {
            this.history = [];
            this.calculateStats();
            this.persist();
            this.notifyListeners({ type: 'cleared' });
            return true;
        }
        return false;
    }
    
    /**
     * Persist to localStorage
     */
    persist() {
        try {
            localStorage.setItem('toolCallHistory', JSON.stringify(this.history));
            localStorage.setItem('toolCallStats', JSON.stringify(this.stats));
        } catch (e) {
            console.error('Failed to persist tool call history:', e);
        }
    }
    
    /**
     * Load from localStorage
     */
    loadHistory() {
        try {
            const stored = localStorage.getItem('toolCallHistory');
            return stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.error('Failed to load tool call history:', e);
            return [];
        }
    }
    
    /**
     * Subscribe to log events
     */
    subscribe(callback) {
        this.listeners.push(callback);
        return () => {
            this.listeners = this.listeners.filter(cb => cb !== callback);
        };
    }
    
    /**
     * Notify listeners
     */
    notifyListeners(data) {
        this.listeners.forEach(callback => {
            try {
                callback(data);
            } catch (e) {
                console.error('Listener error:', e);
            }
        });
    }
}

// Global instance
window.toolLogger = new ToolCallLogger();

console.log('🔧 Tool Call Logger initialized:', window.toolLogger.getStats());
