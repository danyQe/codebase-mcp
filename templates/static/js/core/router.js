/**
 * Section Router
 * Handles navigation between different sections
 */

class SectionRouter {
    constructor() {
        this.currentSection = 'dashboard';
        this.sectionCache = {};
    }
    
    /**
     * Load and display section
     */
    async loadSection(sectionName) {
        // Update state
        appState.set('currentSection', sectionName);
        this.currentSection = sectionName;
        
        // Update URL hash
        window.location.hash = sectionName;
        
        // Update active navigation
        this.updateActiveNav(sectionName);
        
        // Update header title
        this.updateSectionTitle(sectionName);
        
        // Load section content
        await componentLoader.loadSection(sectionName);
        
        // Close sidebar on mobile
        if (window.innerWidth < 1024) {
            closeSidebar();
        }
        
        // Emit event
        eventBus.emit('sectionChanged', sectionName);
        
        // Initialize section-specific functionality
        this.initSection(sectionName);
    }
    
    /**
     * Update active navigation item
     */
    updateActiveNav(section) {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.classList.remove('bg-sidebarHover', 'border-l-4', 'border-blue-500');
        });
        
        // Find and activate matching item
        const activeButton = Array.from(navItems).find(btn => 
            btn.getAttribute('onclick')?.includes(section)
        );
        
        if (activeButton) {
            activeButton.classList.add('bg-sidebarHover', 'border-l-4', 'border-blue-500');
        }
    }
    
    /**
     * Update section title in header
     */
    updateSectionTitle(section) {
        const titles = {
            'dashboard': { text: 'Dashboard Overview', icon: 'chart-line' },
            'search': { text: 'Search & Index', icon: 'search' },
            'files': { text: 'File Operations', icon: 'file-code' },
            'git': { text: 'Git & Sessions', icon: 'code-branch' },
            'memory': { text: 'Memory System', icon: 'brain' },
            'project': { text: 'Project Explorer', icon: 'project-diagram' },
            'directory': { text: 'Directory Browser', icon: 'folder-tree' },
            'working-directory': { text: 'Working Directory', icon: 'folder-open' },
            'logs': { text: 'System Logs', icon: 'clipboard-list' },
            'settings': { text: 'Settings', icon: 'cog' }
        };
        
        const titleData = titles[section] || { text: section, icon: 'file' };
        
        document.getElementById('sectionTitleText').textContent = titleData.text;
        document.getElementById('sectionIcon').className = `fas fa-${titleData.icon} mr-2 text-primary`;
    }
    
    /**
     * Initialize section-specific functionality
     */
    async initSection(section) {
        // Call section-specific init function if exists
        const initFunctionName = `init${section.charAt(0).toUpperCase() + section.slice(1).replace('-', '')}`;
        
        if (typeof window[initFunctionName] === 'function') {
            try {
                await window[initFunctionName]();
            } catch (e) {
                console.error(`Failed to initialize section ${section}:`, e);
            }
        }
    }
    
    /**
     * Navigate to previous section
     */
    goBack() {
        window.history.back();
    }
}

// Global instance
window.router = new SectionRouter();

// Global function for onclick handlers
window.loadSection = (section) => router.loadSection(section);

// Handle browser back/forward
window.addEventListener('hashchange', () => {
    const section = window.location.hash.slice(1) || 'dashboard';
    if (section !== router.currentSection) {
        router.loadSection(section);
    }
});

console.log('🔧 Section Router initialized');
