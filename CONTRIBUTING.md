# Contributing to Codebase MCP

First off, thank you for considering contributing to Codebase MCP! It's people like you that make this tool better for the entire community.

## 🌟 Vision

Codebase MCP aims to democratize AI-powered coding assistance by making it accessible to anyone with a Claude subscription. We're building a privacy-first, extensible platform that can connect any LLM to your codebase through the Model Context Protocol.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Guidelines](#coding-guidelines)
- [Testing Requirements](#testing-requirements)
- [Submitting Changes](#submitting-changes)
- [Priority Areas](#priority-areas)
- [Community](#community)

## 📜 Code of Conduct

This project and everyone participating in it is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## 🤝 How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, include as many details as possible:

**Bug Report Template:**
```markdown
**Description:**
A clear description of the bug

**Steps to Reproduce:**
1. Step one
2. Step two
3. ...

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Environment:**
- OS: [e.g., Windows 11, macOS 14, Ubuntu 22.04]
- Python Version: [e.g., 3.11.5]
- Codebase MCP Version: [e.g., v1.0.0-beta]
- Claude Desktop Version: [if applicable]

**Logs:**
```
Paste relevant error logs here
```

**Additional Context:**
Any other relevant information
```

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Use case**: Why is this enhancement needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: What other approaches did you think about?
- **Implementation ideas**: Any technical suggestions?

### Your First Code Contribution

Unsure where to begin? Look for issues labeled:
- `good first issue` - Simple issues perfect for newcomers
- `help wanted` - Issues where we'd love community help
- `documentation` - Improvements to docs

### Pull Requests

1. Fork the repo and create your branch from `main`
2. Follow the [development setup](#development-setup) instructions
3. Make your changes following our [coding guidelines](#coding-guidelines)
4. Add tests for your changes (if applicable)
5. Ensure all tests pass
6. Update documentation as needed
7. Submit a pull request with a clear description

## 🛠️ Development Setup

### Prerequisites

- **Python 3.11+** (3.11 or 3.12 recommended)
- **Git** for version control
- **uv** package manager (recommended)
- **Claude Desktop** for testing MCP integration

### Setup Steps

1. **Clone your fork:**
```bash
git clone https://github.com/YOUR_USERNAME/codebase-mcp.git
cd codebase-mcp
```

2. **Create virtual environment:**
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# OR using standard venv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3. **Install dependencies:**
```bash
# Using uv
uv pip install -r requirements.txt

# OR using pip
pip install -r requirements.txt

# Install formatters globally
pip install black ruff pytest pytest-asyncio
```

4. **Configure environment:**
```bash
cp .env.example .env
# Add your GEMINI_API_KEY to .env
```

5. **Run tests:**
```bash
pytest tests/
```

6. **Start development server:**
```bash
python main.py /path/to/test/project
```

## 📁 Project Structure

```
codebase-mcp/
├── api/                    # API routers (FastAPI endpoints)
│   └── v1/
│       └── routers/        # Individual route handlers
├── chunkers/               # Code chunking for different languages
│   ├── base.py
│   ├── python_chunker.py
│   └── js_chunker.py
├── code_tools/             # Code manipulation tools
│   ├── formatter.py        # Auto-formatting (Black, Ruff, Prettier)
│   ├── dependency_checker.py
│   ├── write_pipeline.py
│   ├── edit_pipeline.py
│   ├── gemini_client.py
│   └── git_manager.py
├── core/                   # Core configuration and dependencies
│   ├── config.py
│   ├── dependencies.py
│   └── lifespan.py
├── memory_system/          # Persistent memory across sessions
│   ├── memory_manager.py
│   ├── models.py
│   └── api_endpoints.py
├── semantic_search/        # AI-powered code search
│   ├── core.py
│   ├── vector_store.py
│   ├── enhanced_search.py
│   └── symbol_reader.py
├── schemas/                # Pydantic models for API
├── utils/                  # Utility functions
├── templates/              # Web dashboard templates
├── docs/                   # Documentation website
├── tests/                  # Test suite
├── main.py                 # FastAPI server entry point
├── mcp_server.py           # MCP server implementation
└── requirements.txt        # Python dependencies
```

## 📝 Coding Guidelines

### Python Style

We follow **PEP 8** with automatic formatting using Black and Ruff:

```python
# Good: Clear, typed, documented
async def search_codebase(
    query: str,
    max_results: int = 10,
    file_pattern: Optional[str] = None
) -> List[SearchResult]:
    """
    Search codebase using semantic embeddings.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        file_pattern: Optional file pattern filter (e.g., "*.py")
    
    Returns:
        List of search results sorted by relevance
        
    Raises:
        SearchError: If embedding model fails
    """
    # Implementation with proper error handling
    try:
        results = await vector_store.search(query, max_results)
        return [SearchResult.from_dict(r) for r in results]
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise SearchError(f"Failed to search codebase: {e}") from e

# Bad: Unclear, untyped, undocumented
def search(q, max=10, pattern=None):
    results = vector_store.search(q, max)
    return results
```

### Key Principles

1. **Type Hints Always**: Every function parameter and return type must be typed
2. **Docstrings Required**: All public functions need comprehensive docstrings
3. **Error Handling**: Use specific exception types with context
4. **Async First**: Use `async/await` for I/O operations
5. **Naming**: `snake_case` for variables/functions, `PascalCase` for classes
6. **Constants**: UPPER_CASE for constants at module level

### Code Quality Standards

- **Quality Score ≥ 0.8**: All new code must pass quality gates
- **No 'any' types**: Avoid Python's `Any` type unless absolutely necessary
- **Test Coverage**: New features should include tests
- **Documentation**: Update docs when changing behavior

### Formatting

```bash
# Format Python code
black .
ruff check --fix .

# Check formatting
black --check .
ruff check .
```

## 🧪 Testing Requirements

### Writing Tests

1. **Unit Tests**: Test individual functions in isolation
2. **Integration Tests**: Test API endpoints with real components
3. **Test Coverage**: Aim for >80% coverage on new code

```python
# Example test structure
import pytest
from semantic_search.core import SemanticSearchEngine

@pytest.mark.asyncio
async def test_semantic_search_basic():
    """Test basic semantic search functionality."""
    # Arrange
    engine = SemanticSearchEngine()
    await engine.initialize()
    
    # Act
    results = await engine.search("authentication function", max_results=5)
    
    # Assert
    assert len(results) <= 5
    assert all(hasattr(r, 'relevance_score') for r in results)
    assert all(0 <= r.relevance_score <= 1 for r in results)

@pytest.mark.asyncio
async def test_semantic_search_empty_query():
    """Test search with empty query raises appropriate error."""
    engine = SemanticSearchEngine()
    
    with pytest.raises(ValueError, match="Query cannot be empty"):
        await engine.search("")
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_semantic_search.py

# Run specific test
pytest tests/test_semantic_search.py::test_basic_search
```

## 📤 Submitting Changes

### Pull Request Process

1. **Branch Naming**:
   - Feature: `feat/add-rust-support`
   - Bug fix: `fix/memory-leak-in-search`
   - Docs: `docs/improve-installation-guide`
   - Refactor: `refactor/simplify-git-manager`

2. **Commit Messages**:
   ```
   type(scope): brief description

   Longer explanation if needed. Explain what changed and why.
   
   - Bullet points for multiple changes
   - Each change should be clear
   
   Fixes #123
   ```

   Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`

3. **Pull Request Template**:
   ```markdown
   ## Description
   Brief description of changes
   
   ## Motivation
   Why is this change needed?
   
   ## Changes Made
   - Change 1
   - Change 2
   
   ## Testing
   How was this tested?
   
   ## Checklist
   - [ ] Code follows project style guidelines
   - [ ] Tests added/updated
   - [ ] Documentation updated
   - [ ] All tests pass locally
   - [ ] No new warnings introduced
   ```

4. **Review Process**:
   - PRs require at least one approval
   - Address review comments
   - Keep PRs focused (one feature/fix per PR)
   - Rebase on main if needed

## 🎯 Priority Areas

We're especially excited about contributions in these areas:

### 1. 🌐 Language Support (High Priority)

**Add support for more programming languages:**
- Java (AST parsing with `javalang`)
- Go (AST parsing with `go/ast`)
- Rust (AST parsing with `tree-sitter`)
- PHP, Ruby, C++, etc.

**What's needed:**
- Create new chunker in `chunkers/` (see `python_chunker.py` as example)
- Add symbol extraction logic
- Update `semantic_search/symbol_reader.py` to support new language
- Add tests for the new language support

**Impact:** Unlocks Codebase MCP for millions more developers

### 2. 🧠 Local LLM Integration (High Priority)

**Replace Gemini API with local models for edit tool:**
- llama.cpp integration
- Ollama support
- LocalAI compatibility
- GPU acceleration with CUDA/MPS

**What's needed:**
- Modify `code_tools/edit_pipeline.py`
- Add configuration for local model endpoints
- Maintain quality while keeping latency acceptable
- Update documentation

**Impact:** True privacy-first solution, no external API calls

### 3. 🔍 Search Improvements (Medium Priority)

**Enhance semantic search algorithms:**
- Implement RAG (Retrieval-Augmented Generation)
- Add code-specific embeddings (CodeBERT, GraphCodeBERT)
- Improve ranking algorithms
- Add fuzzy matching improvements
- Implement hybrid search (semantic + keyword)

**What's needed:**
- Experiment with different embedding models
- Profile performance impact
- A/B test result quality
- Benchmark against baselines

**Impact:** Better code discovery, more relevant results

### 4. 📊 UI/UX Improvements (Medium Priority)

**Improve web dashboard at localhost:6789:**
- Real-time code visualization
- Interactive search interface
- Memory browser/editor
- Session management UI
- Quality score visualizations

**What's needed:**
- Modern React/Next.js frontend
- WebSocket for real-time updates
- Responsive design
- Accessibility improvements

**Impact:** Better developer experience, easier debugging

### 5. ⚡ Performance Optimizations (Medium Priority)

**Scale to larger codebases (>20k lines):**
- Incremental indexing (index only changed files)
- Parallel processing
- Memory-efficient vector storage
- Lazy loading for large projects
- Caching strategies

**What's needed:**
- Profile current bottlenecks
- Implement optimizations
- Benchmark improvements
- Add performance tests

**Impact:** Support enterprise-scale codebases

### 6. 📚 Documentation & Examples (Ongoing)

**Improve documentation:**
- More usage examples
- Video tutorials
- Best practices guide
- Troubleshooting FAQ
- API reference improvements

**What's needed:**
- Write clear, beginner-friendly guides
- Create example projects
- Record demo videos
- Update existing docs

**Impact:** Easier onboarding, fewer support questions

### 7. 🔌 MCP Ecosystem (Future)

**Expand MCP capabilities:**
- Additional MCP tools
- Better prompt engineering templates
- Integration with other MCP servers
- Custom tool development guide

**What's needed:**
- Explore MCP protocol capabilities
- Design new tools
- Document tool development
- Create examples

**Impact:** Richer ecosystem, more capabilities

## 🌍 Community

### Getting Help

- **GitHub Discussions**: Ask questions, share ideas
- **GitHub Issues**: Report bugs, request features
- **Documentation**: https://danyqe.github.io/codebase-mcp/

### Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in documentation for major contributions

### Code of Conduct

We are committed to providing a welcoming and inspiring community for all. Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## 📜 License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

## 🙏 Thank You!

Your contributions make Codebase MCP better for everyone. Whether you're fixing a typo, adding a feature, or improving documentation - every contribution matters!

---

**Questions?** Open a GitHub Discussion or reach out to the maintainers.

**Ready to contribute?** Pick an issue, fork the repo, and let's build something amazing together! 🚀
