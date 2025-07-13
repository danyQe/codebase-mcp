# 🚀 Codebase Manager MCP Server

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Claude](https://img.shields.io/badge/Claude-Compatible-orange.svg)
![VS Code](https://img.shields.io/badge/VS%20Code-Compatible-blue.svg)

> **Transform your AI coding workflow with powerful codebase management through Model Context Protocol (MCP)**

A comprehensive **Model Context Protocol (MCP) server** that enables **Claude AI**, **VS Code Copilot**, and other MCP-compatible AI assistants to seamlessly interact with your codebase. Perform file operations, Git version control, command execution, and project analysis—all through natural language commands.

## 🌟 Key Features

### 📁 **Complete File System Management**
- **Read, write, create, and delete files** with AI assistance
- **Directory listing and navigation** with detailed file information
- **Smart file search** with content scanning capabilities
- **Secure path validation** preventing unauthorized access

### 🌿 **Advanced Git Integration**
- **Real-time Git status** monitoring and reporting
- **Branch management** - create, switch, delete, and list branches
- **Commit operations** with staged and unstaged change tracking
- **Diff visualization** for files and branches
- **Commit history** browsing with detailed logs

### ⚡ **Command Execution Engine**
- **Safe command execution** with whitelisted commands
- **Built-in test runners** for multiple frameworks
- **Development tool integration** (pytest, black, flake8, mypy)
- **Package manager support** (npm, pip, cargo, etc.)

### 📊 **Project Intelligence**
- **Dependency analysis** across multiple project types
- **Project structure visualization** with tree-like display
- **Automated project detection** (Python, Node.js, Rust, Java)
- **Real-time project metrics** and information

## 🎯 Perfect For

- **AI-Powered Development** - Let Claude manage your codebase
- **Code Review Assistance** - Automated analysis and suggestions
- **Project Documentation** - Generate docs from codebase analysis
- **Debugging Support** - AI-assisted troubleshooting
- **Team Collaboration** - Shared codebase understanding
- **Learning & Education** - Explore codebases with AI guidance

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+** 
- **Git** (for version control features)
- **Claude Desktop** or **VS Code** with Copilot
- **UV** (recommended) or **pip** for package management

### 🔧 Installation

#### Option 1: Using UV (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/codebase-manager-mcp.git
cd codebase-manager-mcp

# Initialize UV project
uv init --name codebase-mcp-server

# Install dependencies
uv add "mcp[cli]" GitPython

# Test the server
uv run python server.py /path/to/your/project
```

#### Option 2: Using Pip

```bash
# Clone the repository
git clone https://github.com/yourusername/codebase-manager-mcp.git
cd codebase-manager-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install "mcp[cli]" GitPython

# Test the server
python server.py /path/to/your/project
```

### ⚙️ Claude Desktop Configuration

Create or edit your Claude Desktop configuration file:

**📍 Configuration File Locations:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "codebase-manager": {
      "command": "python",
      "args": ["/absolute/path/to/server.py", "/path/to/your/project"],
      "env": {}
    }
  }
}
```

#### For UV Users:

```json
{
  "mcpServers": {
    "codebase-manager": {
      "command": "uv",
      "args": [
        "run", 
        "--project", "/path/to/codebase-manager-mcp",
        "python", "server.py",
        "/path/to/your/project"
      ],
      "env": {}
    }
  }
}
```

### 🎮 VS Code Integration

Create `.vscode/mcp.json` in your project:

```json
{
  "mcp": {
    "servers": {
      "codebase-manager": {
        "command": "python",
        "args": ["/path/to/server.py", "${workspaceFolder}"]
      }
    }
  }
}
```

## 💡 Usage Examples

Once configured, interact with your codebase using natural language:

### 📁 File Operations
```
"List all Python files in the src directory"
"Read the contents of main.py"
"Create a new file called utils.py with helper functions"
"Search for files containing 'database' in their name"
"Show me the project structure"
```

### 🌿 Git Operations
```
"What's my current git status?"
"Show me the files I've modified"
"Commit all changes with message 'Add new feature'"
"Create a new branch called 'feature-auth'"
"Show me the last 5 commits"
"What's the diff for auth.py?"
```

### ⚡ Development Commands
```
"Run the test suite"
"Execute npm install"
"Check code style with flake8"
"Run black formatter on all Python files"
"Show me Python version"
```

### 📊 Project Analysis
```
"What dependencies does this project have?"
"Analyze the project structure"
"Show me project information"
"Find all TODO comments in the codebase"
```

## 🛠️ Available Tools

| Tool | Description | Example Usage |
|------|-------------|---------------|
| `read_file` | Read file contents | "Read the README.md file" |
| `write_file` | Write to files | "Update config.py with new settings" |
| `list_directory` | Browse directories | "List all files in the src folder" |
| `search_files` | Find files by pattern | "Find all .js files containing 'api'" |
| `git_status` | Git repository status | "What's my git status?" |
| `git_commit` | Create commits | "Commit changes with message" |
| `git_branch_operations` | Branch management | "Create branch feature-x" |
| `execute_command` | Run commands | "Run pytest on the tests folder" |

## 🔒 Security Features

- **Path Validation**: Prevents access outside project directory
- **Command Whitelisting**: Only allows safe, pre-approved commands
- **Timeout Protection**: Commands timeout after 30 seconds
- **Error Handling**: Comprehensive error reporting and recovery
- **Permission Boundaries**: Respects file system permissions

## 📋 Project Structure

```
codebase-manager-mcp/
├── server.py                 # Main MCP server
├── setup.py                  # Auto-configuration script
├── requirements.txt         # Pip dependencies
├── README.md               # This file
├── LICENSE                 # MIT License
```

## 🔧 Advanced Configuration

### Multiple Projects

Configure multiple projects simultaneously:

```json
{
  "mcpServers": {
    "project-frontend": {
      "command": "python",
      "args": ["/path/to/server.py", "/path/to/frontend"],
      "env": {}
    },
    "project-backend": {
      "command": "python", 
      "args": ["/path/to/server.py", "/path/to/backend"],
      "env": {}
    }
  }
}
```

### Environment Variables

```json
{
  "mcpServers": {
    "codebase-manager": {
      "command": "python",
      "args": ["/path/to/server.py", "${PROJECT_DIR}"],
      "env": {
        "PROJECT_DIR": "/current/project/path",
        "PYTHONPATH": "/custom/python/path"
      }
    }
  }
}
```

### Custom Command Whitelist

Modify the `ALLOWED_COMMANDS` in `server.py`:

```python
ALLOWED_COMMANDS = {
    'python', 'python3', 'pip', 'pip3',
    'node', 'npm', 'yarn', 'pnpm',
    'pytest', 'black', 'flake8', 'mypy',
    'docker', 'docker-compose',
    'your-custom-command'  # Add your commands here
}
```

## 🚨 Troubleshooting

### Common Issues

#### ❌ Import Error: No module named 'mcp'
```bash
# Install MCP SDK
pip install "mcp[cli]"
# or with UV
uv add "mcp[cli]"
```

#### ❌ Git operations not working
```bash
# Install GitPython
pip install GitPython
# or with UV  
uv add GitPython
```

#### ❌ Server not connecting to Claude
1. Check file paths in configuration
2. Restart Claude Desktop completely
3. Verify Python is in system PATH
4. Test server manually: `python server.py /test/path`

#### ❌ Permission denied errors
- Ensure the project directory exists and is accessible
- Check file permissions
- Verify paths are correctly specified

### Debug Mode

Test your server locally before connecting to Claude:

```bash
# Test with MCP inspector
mcp dev server.py /path/to/project

# Manual testing
python server.py /path/to/project --debug
```

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature-name`
3. **Make** your changes and add tests
4. **Ensure** all tests pass: `pytest tests/`
5. **Commit** your changes: `git commit -m 'Add feature'`
6. **Push** to your branch: `git push origin feature-name`
7. **Submit** a pull request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/danyQe/codebase-mcp.git
cd codebase-mcp

# Install development dependencies
uv add --dev pytest black flake8 mypy

# Run tests
uv run pytest

# Format code
uv run black .

# Type checking
uv run mypy server.py
```

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## 🌟 Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/codebase-manager-mcp&type=Date)](https://star-history.com/#yourusername/codebase-manager-mcp&Date)

## 🙏 Acknowledgments

- **Anthropic** for creating the Model Context Protocol
- **Claude AI** for inspiring this integration
- **Open Source Community** for continuous support and contributions

## 📞 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/yourusername/codebase-manager-mcp/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/yourusername/codebase-manager-mcp/discussions)
- 📧 **Email**: your.email@example.com
- 💬 **Discord**: [Join our community](https://discord.gg/your-invite)

## 🏷️ Tags

`mcp` `model-context-protocol` `claude-ai` `ai-development` `codebase-management` `git-integration` `python` `automation` `developer-tools` `ai-assistant` `vs-code` `file-management` `code-analysis` `ai-coding` `productivity`

---

<div align="center">

**⭐ Star this repository if it helped you!**

*Built with ❤️ for the AI development community*

[Report Bug](https://github.com/danyQe/codebase-mcp/issues) • [Request Feature]([https://github.com/yourusername/codebase-manager-mcp](https://github.com/danyQe/codebase-mcp)/issues) )

</div>
