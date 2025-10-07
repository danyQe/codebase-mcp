/**
 * Toast Notification System
 * Beautiful toast notifications for user feedback
 */

class NotificationSystem {
    constructor() {
        this.container = document.getElementById('toast-container');
        this.notifications = [];
    }
    
    /**
     * Show notification
     */
    show(message, type = 'info', duration = 5000) {
        const id = Date.now() + Math.random();
        
        const notification = {
            id,
            message,
            type,
            timestamp: new Date()
        };
        
        this.notifications.push(notification);
        this.render(notification, duration);
        
        return id;
    }
    
    /**
     * Show success notification
     */
    success(message, duration = 3000) {
        return this.show(message, 'success', duration);
    }
    
    /**
     * Show error notification
     */
    error(message, duration = 7000) {
        return this.show(message, 'error', duration);
    }
    
    /**
     * Show warning notification
     */
    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }
    
    /**
     * Show info notification
     */
    info(message, duration = 4000) {
        return this.show(message, 'info', duration);
    }
    
    /**
     * Render notification
     */
    render(notification, duration) {
        const toast = document.createElement('div');
        toast.id = `toast-${notification.id}`;
        toast.className = this.getToastClasses(notification.type);
        
        const icon = this.getIcon(notification.type);
        
        toast.innerHTML = `
            <div class="flex items-start">
                <div class="flex-shrink-0">
                    ${icon}
                </div>
                <div class="ml-3 flex-1">
                    <p class="text-sm font-medium">${this.escapeHtml(notification.message)}</p>
                </div>
                <button onclick="notifications.dismiss(${notification.id})" class="ml-4 flex-shrink-0 text-gray-400 hover:text-gray-500">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        this.container.appendChild(toast);
        
        // Animate in
        setTimeout(() => toast.classList.add('opacity-100', 'translate-y-0'), 10);
        
        // Auto-dismiss
        if (duration > 0) {
            setTimeout(() => this.dismiss(notification.id), duration);
        }
    }
    
    /**
     * Get toast classes based on type
     */
    getToastClasses(type) {
        const baseClasses = 'opacity-0 translate-y-2 transition-all duration-300 max-w-md w-full shadow-lg rounded-lg p-4 mb-2';
        
        const typeClasses = {
            success: 'bg-green-50 border border-green-200',
            error: 'bg-red-50 border border-red-200',
            warning: 'bg-yellow-50 border border-yellow-200',
            info: 'bg-blue-50 border border-blue-200'
        };
        
        return `${baseClasses} ${typeClasses[type] || typeClasses.info}`;
    }
    
    /**
     * Get icon HTML for notification type
     */
    getIcon(type) {
        const icons = {
            success: '<i class="fas fa-check-circle text-green-500 text-xl"></i>',
            error: '<i class="fas fa-exclamation-circle text-red-500 text-xl"></i>',
            warning: '<i class="fas fa-exclamation-triangle text-yellow-500 text-xl"></i>',
            info: '<i class="fas fa-info-circle text-blue-500 text-xl"></i>'
        };
        
        return icons[type] || icons.info;
    }
    
    /**
     * Dismiss notification
     */
    dismiss(id) {
        const toast = document.getElementById(`toast-${id}`);
        if (toast) {
            toast.classList.remove('opacity-100', 'translate-y-0');
            toast.classList.add('opacity-0', 'translate-y-2');
            setTimeout(() => toast.remove(), 300);
        }
        
        this.notifications = this.notifications.filter(n => n.id !== id);
    }
    
    /**
     * Clear all notifications
     */
    clearAll() {
        this.notifications.forEach(n => this.dismiss(n.id));
    }
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance
window.notifications = new NotificationSystem();

console.log('🔧 Notification System initialized');
