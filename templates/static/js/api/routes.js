/**
 * API Routes - All available endpoints from refactored FastAPI backend
 * Complete utilization of all routes
 */

const API_ROUTES = {
    // ============================================================================
    // HEALTH & STATUS
    // ============================================================================
    health: {
        check: () => api.get('/health', { userAction: 'Health Check' }),
        status: () => api.get('/status', { userAction: 'Get Status' }),
    },
    
    // ============================================================================
    // WORKING DIRECTORY MANAGEMENT
    // ============================================================================
    workingDirectory: {
        get: () => api.get('/working-directory', { userAction: 'Get Working Directory' }),
        
        validate: (dirPath) => api.post('/working-directory/validate', 
            { working_directory: dirPath },
            { userAction: 'Validate Directory' }
        ),
        
        change: (dirPath) => api.put('/working-directory',
            { working_directory: dirPath },
            { userAction: 'Change Working Directory' }
        ),
    },
    
    // ============================================================================
    // SEARCH OPERATIONS
    // ============================================================================
    search: {
        semantic: (query, options = {}) => api.post('/search',
            {
                query,
                search_type: 'semantic',
                file_pattern: options.filePattern || null,
                max_results: options.maxResults || 10
            },
            { userAction: 'Semantic Search' }
        ),
        
        text: (query, options = {}) => api.post('/search/text',
            null,
            {
                params: {
                    query,
                    file_pattern: options.filePattern || '*.py',
                    use_regex: options.useRegex || false,
                    case_sensitive: options.caseSensitive || false,
                    max_results: options.maxResults || 50
                },
                userAction: 'Text Search'
            }
        ),
        
        symbols: (query, options = {}) => api.post('/search/symbols',
            null,
            {
                params: {
                    query,
                    symbol_type: options.symbolType || null,
                    file_pattern: options.filePattern || null,
                    fuzzy: options.fuzzy !== false,
                    min_score: options.minScore || 0.5,
                    max_results: options.maxResults || 20
                },
                userAction: 'Symbol Search'
            }
        ),
        
        index: () => api.post('/search/index', null, { userAction: 'Rebuild Index' }),
        
        stats: () => api.get('/search/stats', { userAction: 'Get Search Stats' }),
        
        updateFile: (filePath) => api.post('/search/update_file',
            null,
            { params: { file_path: filePath }, userAction: 'Update File Index' }
        ),
        
        listFileSymbols: (filePath) => api.get(`/search/symbols/${filePath}`, 
            { userAction: 'List File Symbols' }
        ),
    },
    
    // ============================================================================
    // FILE OPERATIONS
    // ============================================================================
    files: {
        read: (filePath, options = {}) => api.post('/read',
            null,
            {
                params: {
                    file_path: filePath,
                    symbol_name: options.symbolName || null,
                    occurrence: options.occurrence || 1,
                    start_line: options.startLine || null,
                    end_line: options.endLine || null,
                    with_line_numbers: options.withLineNumbers !== false
                },
                userAction: 'Read Code'
            }
        ),
        
        write: (filePath, content, options = {}) => api.post('/write',
            {
                file_path: filePath,
                content,
                purpose: options.purpose || null,
                language: options.language || null,
                save_to_file: options.saveToFile !== false
            },
            { userAction: 'Write File' }
        ),
        
        edit: (targetFile, instructions, codeEdit, options = {}) => api.post('/edit',
            {
                target_file: targetFile,
                instructions,
                code_edit: codeEdit,
                language: options.language || null,
                save_to_file: options.saveToFile !== false
            },
            { userAction: 'AI Edit File' }
        ),
        
        writeStats: () => api.get('/write/stats', { userAction: 'Get Write Stats' }),
        
        editStats: () => api.get('/edit/stats', { userAction: 'Get Edit Stats' }),
    },
    
    // ============================================================================
    // GIT OPERATIONS
    // ============================================================================
    git: {
        status: () => api.post('/git', 
            { operation: 'status' },
            { userAction: 'Git Status' }
        ),
        
        branches: () => api.post('/git',
            { operation: 'branches' },
            { userAction: 'Git Branches' }
        ),
        
        log: (options = {}) => api.post('/git',
            {
                operation: 'log',
                max_results: options.maxResults || 10,
                file_path: options.filePath || null
            },
            { userAction: 'Git Log' }
        ),
        
        diff: (options = {}) => api.post('/git',
            {
                operation: 'diff',
                file_path: options.filePath || null,
                cached: options.cached || false
            },
            { userAction: 'Git Diff' }
        ),
        
        add: (files) => api.post('/git',
            {
                operation: 'add',
                files: Array.isArray(files) ? files : [files]
            },
            { userAction: 'Git Add' }
        ),
        
        commit: (message, files = null) => api.post('/git',
            {
                operation: 'commit',
                message,
                files
            },
            { userAction: 'Git Commit' }
        ),
        
        blame: (filePath) => api.post('/git',
            { operation: 'blame', file_path: filePath },
            { userAction: 'Git Blame' }
        ),
        
        tree: () => api.post('/git/tree',
            { operation: 'tree' },
            { userAction: 'Git Tree' }
        ),
    },
    
    // ============================================================================
    // SESSION MANAGEMENT
    // ============================================================================
    session: {
        start: (sessionName = null) => api.post('/session',
            {
                operation: 'start',
                session_name: sessionName
            },
            { userAction: 'Start Session' }
        ),
        
        end: (autoMerge = false, message = null) => api.post('/session',
            {
                operation: 'end',
                auto_merge: autoMerge,
                message
            },
            { userAction: 'End Session' }
        ),
        
        switch: (sessionName) => api.post('/session',
            {
                operation: 'switch',
                session_name: sessionName
            },
            { userAction: 'Switch Session' }
        ),
        
        list: () => api.post('/session',
            { operation: 'list' },
            { userAction: 'List Sessions' }
        ),
        
        merge: (sessionName, message = null) => api.post('/session',
            {
                operation: 'merge',
                session_name: sessionName,
                message
            },
            { userAction: 'Merge Session' }
        ),
        
        delete: (sessionName) => api.post('/session',
            {
                operation: 'delete',
                session_name: sessionName
            },
            { userAction: 'Delete Session' }
        ),
        
        current: () => api.get('/session/current', { userAction: 'Get Current Session' }),
        
        autoCommit: (filePath, operation, purpose = null, qualityScore = null) => 
            api.post('/session/auto-commit',
                null,
                {
                    params: {
                        file_path: filePath,
                        operation,
                        purpose,
                        quality_score: qualityScore
                    },
                    userAction: 'Auto Commit'
                }
            ),
    },
    
    // ============================================================================
    // MEMORY SYSTEM
    // ============================================================================
    memory: {
        store: (category, content, options = {}) => api.post('/memory/store',
            {
                category,
                content,
                subcategory: options.subcategory || null,
                importance: options.importance || 3,
                session_id: options.sessionId || null,
                tags: options.tags || [],
                context: options.context || {},
                related_files: options.relatedFiles || []
            },
            { userAction: 'Store Memory' }
        ),
        
        search: (query, options = {}) => api.post('/memory/search',
            {
                query,
                category: options.category || null,
                subcategory: options.subcategory || null,
                min_importance: options.minImportance || 1,
                max_results: options.maxResults || 10,
                include_archived: options.includeArchived || false,
                recent_days: options.recentDays || null
            },
            { userAction: 'Search Memory' }
        ),
        
        context: (sessionId = null) => api.get('/memory/context',
            {
                params: sessionId ? { session_id: sessionId } : {},
                userAction: 'Get Memory Context'
            }
        ),
        
        update: (memoryId, updates) => api.put(`/memory/${memoryId}`,
            updates,
            { userAction: 'Update Memory' }
        ),
        
        stats: () => api.get('/memory/stats', { userAction: 'Get Memory Stats' }),
        
        archive: (memoryId) => api.delete(`/memory/${memoryId}`,
            { userAction: 'Archive Memory' }
        ),
        
        list: (options = {}) => api.get('/memory/list',
            {
                params: {
                    category: options.category || null,
                    importance_min: options.importanceMin || 1,
                    importance_max: options.importanceMax || 5,
                    limit: options.limit || 50,
                    offset: options.offset || 0,
                    sort_by: options.sortBy || 'timestamp',
                    sort_order: options.sortOrder || 'desc'
                },
                userAction: 'List Memories'
            }
        ),
    },
    
    // ============================================================================
    // PROJECT & DIRECTORY
    // ============================================================================
    project: {
        context: (operation, options = {}) => api.get('/project/context',
            {
                params: {
                    operation,
                    max_depth: options.maxDepth || 5,
                    include_hidden: options.includeHidden || false
                },
                userAction: `Project ${operation}`
            }
        ),
        
        info: () => api.get('/project/context',
            { params: { operation: 'info' }, userAction: 'Get Project Info' }
        ),
        
        structure: (maxDepth = 5) => api.get('/project/context',
            {
                params: { operation: 'structure', max_depth: maxDepth },
                userAction: 'Get Project Structure'
            }
        ),
        
        dependencies: () => api.get('/project/context',
            { params: { operation: 'dependencies' }, userAction: 'Get Dependencies' }
        ),
    },
    
    directory: {
        list: (dirPath = '.', options = {}) => api.get('/directory/list',
            {
                params: {
                    directory_path: dirPath,
                    max_depth: options.maxDepth || 2,
                    include_hidden: options.includeHidden || false,
                    show_metadata: options.showMetadata !== false,
                    respect_gitignore: options.respectGitignore !== false,
                    files_only: options.filesOnly || false,
                    dirs_only: options.dirsOnly || false
                },
                userAction: 'List Directory'
            }
        ),
        
        tree: (dirPath = '.', maxDepth = 3) => api.get(`/directory/tree/${dirPath}`,
            {
                params: { max_depth: maxDepth },
                userAction: 'Get Directory Tree'
            }
        ),
    },
    
    // ============================================================================
    // LOGS & MONITORING
    // ============================================================================
    logs: {
        get: (options = {}) => {
            // Filter out null/undefined values
            const params = {};
            if (options.level) params.level = options.level;
            if (options.component) params.component = options.component;
            if (options.limit) params.limit = options.limit;
            if (options.since) params.since = options.since;
            
            return api.get('/logs', {
                params,
                userAction: 'Get Logs'
            });
        },
        
        clear: () => api.delete('/logs', { userAction: 'Clear Logs' }),
        
        performance: () => api.get('/monitoring/performance', 
            { userAction: 'Get Performance Metrics' }
        ),
    },
};

// Export for global access
window.apiRoutes = API_ROUTES;

console.log('🔧 API Routes configured:', Object.keys(API_ROUTES).length, 'route groups');