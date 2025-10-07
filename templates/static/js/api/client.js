/**
 * API Client with automatic tool call logging
 * All API calls automatically recorded via interceptor
 */

class APIClient {
    constructor(baseURL = 'http://localhost:6789') {
        this.baseURL = baseURL;
        this.defaultHeaders = {
            'Content-Type': 'application/json'
        };
    }
    
    /**
     * Make API request with automatic logging
     */
    async request(method, endpoint, options = {}) {
        const startTime = Date.now();
        const fullURL = `${this.baseURL}${endpoint}`;
        
        const requestData = {
            method,
            headers: { ...this.defaultHeaders, ...options.headers },
        };
        
        if (options.body) {
            requestData.body = JSON.stringify(options.body);
        }
        
        if (options.params) {
            const params = new URLSearchParams(options.params);
            endpoint += `?${params.toString()}`;
        }
        
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, requestData);
            const duration = Date.now() - startTime;
            const data = await response.json();
            
            // Log this call
            window.toolLogger.log({
                route: endpoint,
                method,
                request: options.body || options.params || null,
                response: data,
                duration,
                status: response.ok ? 'success' : 'error',
                statusCode: response.status,
                error: response.ok ? null : data.error || 'Request failed',
                userAction: options.userAction || 'API Call',
                context: options.context || {}
            });
            
            if (!response.ok) {
                throw new Error(data.error || `Request failed with status ${response.status}`);
            }
            
            return { success: true, data, statusCode: response.status };
            
        } catch (error) {
            const duration = Date.now() - startTime;
            
            // Log error
            window.toolLogger.log({
                route: endpoint,
                method,
                request: options.body || options.params || null,
                response: null,
                duration,
                status: 'error',
                statusCode: 0,
                error: error.message,
                userAction: options.userAction || 'API Call',
                context: options.context || {}
            });
            
            return { success: false, error: error.message };
        }
    }
    
    /**
     * GET request
     */
    async get(endpoint, options = {}) {
        return this.request('GET', endpoint, options);
    }
    
    /**
     * POST request
     */
    async post(endpoint, body, options = {}) {
        return this.request('POST', endpoint, { ...options, body });
    }
    
    /**
     * PUT request
     */
    async put(endpoint, body, options = {}) {
        return this.request('PUT', endpoint, { ...options, body });
    }
    
    /**
     * DELETE request
     */
    async delete(endpoint, options = {}) {
        return this.request('DELETE', endpoint, options);
    }
    
    /**
     * Update base URL
     */
    setBaseURL(url) {
        this.baseURL = url;
    }
}

// Global instance
window.api = new APIClient();

console.log('🔧 API Client initialized');
