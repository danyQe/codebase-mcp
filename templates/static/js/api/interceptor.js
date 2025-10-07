/**
 * API Request/Response Interceptor
 * Enhances API calls with automatic error handling and retry logic
 */

class APIInterceptor {
    constructor() {
        this.requestInterceptors = [];
        this.responseInterceptors = [];
    }
    
    /**
     * Add request interceptor
     */
    addRequestInterceptor(callback) {
        this.requestInterceptors.push(callback);
    }
    
    /**
     * Add response interceptor
     */
    addResponseInterceptor(callback) {
        this.responseInterceptors.push(callback);
    }
    
    /**
     * Process request through interceptors
     */
    async processRequest(config) {
        let processedConfig = { ...config };
        
        for (const interceptor of this.requestInterceptors) {
            try {
                processedConfig = await interceptor(processedConfig);
            } catch (e) {
                console.error('Request interceptor error:', e);
            }
        }
        
        return processedConfig;
    }
    
    /**
     * Process response through interceptors
     */
    async processResponse(response) {
        let processedResponse = response;
        
        for (const interceptor of this.responseInterceptors) {
            try {
                processedResponse = await interceptor(processedResponse);
            } catch (e) {
                console.error('Response interceptor error:', e);
            }
        }
        
        return processedResponse;
    }
}

// Global interceptor instance
const interceptor = new APIInterceptor();

// Add default request interceptor - add timestamp
interceptor.addRequestInterceptor((config) => {
    config.timestamp = Date.now();
    return config;
});

// Add default response interceptor - handle common errors
interceptor.addResponseInterceptor((response) => {
    // Log errors to console
    if (!response.success) {
        console.error('API Error:', response.error);
    }
    
    return response;
});

// Add interceptor for connection errors
interceptor.addResponseInterceptor((response) => {
    if (!response.success && response.error?.includes('Failed to fetch')) {
        appState.set('connected', false);
        notifications.error('Connection lost to API server');
    } else if (response.success && !appState.get('connected')) {
        appState.set('connected', true);
        notifications.success('Connection restored');
    }
    
    return response;
});

window.apiInterceptor = interceptor;

console.log('🔧 API Interceptor initialized');
