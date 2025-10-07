/**
 * LocalStorage Utilities
 * Helpers for storing and retrieving data
 */

const storageUtils = {
    /**
     * Get item from localStorage with fallback
     */
    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.error(`Failed to get ${key} from localStorage:`, e);
            return defaultValue;
        }
    },
    
    /**
     * Set item in localStorage
     */
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error(`Failed to set ${key} in localStorage:`, e);
            return false;
        }
    },
    
    /**
     * Remove item from localStorage
     */
    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (e) {
            console.error(`Failed to remove ${key} from localStorage:`, e);
            return false;
        }
    },
    
    /**
     * Clear all localStorage
     */
    clear() {
        try {
            localStorage.clear();
            return true;
        } catch (e) {
            console.error('Failed to clear localStorage:', e);
            return false;
        }
    },
    
    /**
     * Check if key exists
     */
    has(key) {
        return localStorage.getItem(key) !== null;
    },
    
    /**
     * Get all keys
     */
    keys() {
        return Object.keys(localStorage);
    }
};

window.storageUtils = storageUtils;

console.log('🔧 Storage Utils initialized');
