/**
 * Formatting Utilities
 * Format data for display in UI
 */

const formatUtils = {
    /**
     * Format bytes to human readable
     */
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    /**
     * Format duration in milliseconds
     */
    formatDuration(ms) {
        if (ms < 1000) return `${ms}ms`;
        if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
        if (ms < 3600000) return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
        return `${Math.floor(ms / 3600000)}h ${Math.floor((ms % 3600000) / 60000)}m`;
    },
    
    /**
     * Format timestamp to relative time
     */
    formatRelativeTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (seconds < 60) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;
        if (days < 30) return `${Math.floor(days / 7)}w ago`;
        if (days < 365) return `${Math.floor(days / 30)}mo ago`;
        return `${Math.floor(days / 365)}y ago`;
    },
    
    /**
     * Format date and time
     */
    formatDateTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString();
    },
    
    /**
     * Format date only
     */
    formatDate(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleDateString();
    },
    
    /**
     * Format time only
     */
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    },
    
    /**
     * Format number with thousand separators
     */
    formatNumber(num) {
        return num.toLocaleString();
    },
    
    /**
     * Format percentage
     */
    formatPercent(value, decimals = 2) {
        return `${parseFloat(value).toFixed(decimals)}%`;
    },
    
    /**
     * Truncate text with ellipsis
     */
    truncate(text, maxLength = 100) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength - 3) + '...';
    },
    
    /**
     * Format JSON with syntax highlighting
     */
    formatJSON(obj, indent = 2) {
        return JSON.stringify(obj, null, indent);
    },
    
    /**
     * Format code with line numbers
     */
    formatCode(code, startLine = 1) {
        const lines = code.split('\n');
        return lines.map((line, idx) => {
            const lineNum = (startLine + idx).toString().padStart(4, ' ');
            return `${lineNum} | ${line}`;
        }).join('\n');
    },
    
    /**
     * Get status badge HTML
     */
    getStatusBadge(status) {
        const badges = {
            success: '<span class="px-2 py-1 text-xs font-medium rounded-full bg-green-100 text-green-800">Success</span>',
            error: '<span class="px-2 py-1 text-xs font-medium rounded-full bg-red-100 text-red-800">Error</span>',
            warning: '<span class="px-2 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-800">Warning</span>',
            pending: '<span class="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800">Pending</span>',
            active: '<span class="px-2 py-1 text-xs font-medium rounded-full bg-purple-100 text-purple-800">Active</span>'
        };
        
        return badges[status] || badges.pending;
    },
    
    /**
     * Get importance stars
     */
    getImportanceStars(importance) {
        return '⭐'.repeat(importance);
    },
    
    /**
     * Get category icon
     */
    getCategoryIcon(category) {
        const icons = {
            learning: '📚',
            progress: '🚀',
            preference: '⚙️',
            mistake: '⚠️',
            solution: '💡',
            architecture: '🏗️',
            integration: '🔗',
            debug: '🐛'
        };
        
        return icons[category] || '📝';
    },
    
    /**
     * Sanitize HTML to prevent XSS
     */
    sanitizeHTML(html) {
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    },
    
    /**
     * Format file size from stats
     */
    formatFileSize(size) {
        if (typeof size === 'string') return size;
        return this.formatBytes(size);
    }
};

// Export globally
window.formatUtils = formatUtils;

console.log('🔧 Format Utils initialized');
