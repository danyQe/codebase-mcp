/**
 * Client-Side Validation Utilities
 * Form validation helpers
 */

const validationUtils = {
    /**
     * Validate file path
     */
    isValidPath(path) {
        if (!path || path.trim() === '') return false;
        
        // Basic path validation
        const invalidChars = ['<', '>', '|', '\0'];
        return !invalidChars.some(char => path.includes(char));
    },
    
    /**
     * Validate directory path
     */
    isValidDirectory(path) {
        if (!this.isValidPath(path)) return false;
        
        // Should not end with a filename extension
        const parts = path.split(/[\\/]/);
        const lastPart = parts[parts.length - 1];
        
        return !lastPart.includes('.');
    },
    
    /**
     * Validate URL
     */
    isValidURL(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    },
    
    /**
     * Validate non-empty string
     */
    isNotEmpty(value) {
        return value && value.trim() !== '';
    },
    
    /**
     * Validate number range
     */
    isInRange(value, min, max) {
        const num = parseFloat(value);
        return !isNaN(num) && num >= min && num <= max;
    },
    
    /**
     * Validate session name
     */
    isValidSessionName(name) {
        if (!name || name.trim() === '') return true; // Optional
        
        // Only alphanumeric, hyphens, underscores
        return /^[a-zA-Z0-9_-]+$/.test(name);
    },
    
    /**
     * Validate commit message
     */
    isValidCommitMessage(message) {
        return this.isNotEmpty(message) && message.length <= 500;
    },
    
    /**
     * Show validation error
     */
    showError(inputId, message) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        input.classList.add('border-red-500');
        
        // Create or update error message
        let errorDiv = input.nextElementSibling;
        if (!errorDiv || !errorDiv.classList.contains('validation-error')) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'validation-error text-red-600 text-xs mt-1';
            input.parentNode.insertBefore(errorDiv, input.nextSibling);
        }
        
        errorDiv.textContent = message;
    },
    
    /**
     * Clear validation error
     */
    clearError(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        input.classList.remove('border-red-500');
        
        const errorDiv = input.nextElementSibling;
        if (errorDiv && errorDiv.classList.contains('validation-error')) {
            errorDiv.remove();
        }
    },
    
    /**
     * Validate form
     */
    validateForm(formId, rules) {
        let isValid = true;
        
        Object.entries(rules).forEach(([fieldId, rule]) => {
            const value = document.getElementById(fieldId)?.value;
            
            if (rule.required && !this.isNotEmpty(value)) {
                this.showError(fieldId, 'This field is required');
                isValid = false;
            } else if (rule.type === 'path' && !this.isValidPath(value)) {
                this.showError(fieldId, 'Invalid path format');
                isValid = false;
            } else if (rule.type === 'url' && !this.isValidURL(value)) {
                this.showError(fieldId, 'Invalid URL format');
                isValid = false;
            } else if (rule.minLength && value.length < rule.minLength) {
                this.showError(fieldId, `Minimum ${rule.minLength} characters required`);
                isValid = false;
            } else if (rule.maxLength && value.length > rule.maxLength) {
                this.showError(fieldId, `Maximum ${rule.maxLength} characters allowed`);
                isValid = false;
            } else {
                this.clearError(fieldId);
            }
        });
        
        return isValid;
    }
};

window.validationUtils = validationUtils;

console.log('🔧 Validation Utils initialized');
