/**
 * Component Loader System
 * Dynamically loads HTML components and manages their lifecycle
 */

class ComponentLoader {
    constructor() {
        this.loadedComponents = {};
        this.componentCache = {};
    }
    
    /**
     * Load component from file
     */
    async loadComponent(name, containerSelector) {
        try {
            const componentPath = `/templates/components/${name}.html`;
            
            // Check cache first
            if (this.componentCache[componentPath]) {
                this.renderComponent(containerSelector, this.componentCache[componentPath]);
                return this.componentCache[componentPath];
            }
            
            const response = await fetch(componentPath);
            
            if (!response.ok) {
                throw new Error(`Failed to load component: ${name}`);
            }
            
            const html = await response.text();
            
            // Cache the component
            this.componentCache[componentPath] = html;
            
            // Render into container
            this.renderComponent(containerSelector, html);
            
            // Mark as loaded
            this.loadedComponents[name] = {
                path: componentPath,
                container: containerSelector,
                loadedAt: new Date()
            };
            
            // Emit event
            this.emitEvent('componentLoaded', { name, container: containerSelector });
            
            return html;
            
        } catch (error) {
            console.error(`Failed to load component ${name}:`, error);
            this.renderError(containerSelector, name);
            return null;
        }
    }
    
    /**
     * Render component HTML into container
     */
    renderComponent(selector, html) {
        const container = document.querySelector(selector);
        if (container) {
            container.innerHTML = html;
            
            // Execute any scripts in the component
            const scripts = container.querySelectorAll('script');
            scripts.forEach(script => {
                const newScript = document.createElement('script');
                newScript.textContent = script.textContent;
                document.body.appendChild(newScript);
                document.body.removeChild(newScript);
            });
        } else {
            console.error(`Container not found: ${selector}`);
        }
    }
    
    /**
     * Render error state
     */
    renderError(selector, componentName) {
        const container = document.querySelector(selector);
        if (container) {
            container.innerHTML = `
                <div class="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
                    <i class="fas fa-exclamation-triangle text-red-500 text-2xl mb-2"></i>
                    <p class="text-red-700 font-medium">Failed to load component: ${componentName}</p>
                </div>
            `;
        }
    }
    
    /**
     * Load multiple components
     */
    async loadComponents(components) {
        const promises = components.map(comp => 
            this.loadComponent(comp.name, comp.container)
        );
        
        return Promise.all(promises);
    }
    
    /**
     * Reload component
     */
    async reloadComponent(name, containerSelector) {
        const componentPath = `/templates/components/${name}.html`;
        delete this.componentCache[componentPath];
        return this.loadComponent(name, containerSelector);
    }
    
    /**
     * Load section content
     */
    async loadSection(sectionName) {
        const sectionPath = `/templates/components/sections/${sectionName}.html`;
        
        try {
            const response = await fetch(sectionPath);
            if (!response.ok) throw new Error(`Section not found: ${sectionName}`);
            
            const html = await response.text();
            const container = document.getElementById('content-container');
            
            if (container) {
                container.innerHTML = html;
                
                // Execute scripts
                const scripts = container.querySelectorAll('script');
                scripts.forEach(script => {
                    const newScript = document.createElement('script');
                    newScript.textContent = script.textContent;
                    document.body.appendChild(newScript);
                    document.body.removeChild(newScript);
                });
                
                // Update state
                window.appState.set('currentSection', sectionName);
                
                // Emit event
                this.emitEvent('sectionLoaded', { section: sectionName });
            }
            
            return html;
            
        } catch (error) {
            console.error(`Failed to load section ${sectionName}:`, error);
            notifications.error(`Failed to load ${sectionName} section`);
            return null;
        }
    }
    
    /**
     * Emit custom event
     */
    emitEvent(eventName, detail) {
        const event = new CustomEvent(eventName, { detail });
        document.dispatchEvent(event);
    }
    
    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance
window.componentLoader = new ComponentLoader();

console.log('🔧 Component Loader initialized');
