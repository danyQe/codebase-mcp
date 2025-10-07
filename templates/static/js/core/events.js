/**
 * Event Bus System
 * Publish-subscribe pattern for component communication
 */

class EventBus {
    constructor() {
        this.events = {};
    }
    
    /**
     * Subscribe to event
     */
    on(eventName, callback) {
        if (!this.events[eventName]) {
            this.events[eventName] = [];
        }
        
        this.events[eventName].push(callback);
        
        // Return unsubscribe function
        return () => {
            this.events[eventName] = this.events[eventName].filter(cb => cb !== callback);
        };
    }
    
    /**
     * Subscribe once
     */
    once(eventName, callback) {
        const unsubscribe = this.on(eventName, (...args) => {
            callback(...args);
            unsubscribe();
        });
        return unsubscribe;
    }
    
    /**
     * Emit event
     */
    emit(eventName, ...args) {
        if (this.events[eventName]) {
            this.events[eventName].forEach(callback => {
                try {
                    callback(...args);
                } catch (e) {
                    console.error(`Event handler error (${eventName}):`, e);
                }
            });
        }
    }
    
    /**
     * Remove all listeners for event
     */
    off(eventName) {
        delete this.events[eventName];
    }
    
    /**
     * Clear all events
     */
    clear() {
        this.events = {};
    }
}

// Global instance
window.eventBus = new EventBus();

console.log('🔧 Event Bus initialized');
