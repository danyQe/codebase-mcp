# codebase_server.py
from mcp.server.fastmcp import FastMCP, Context
import os
import sys
import subprocess
import threading
from typing import List
import subprocess
import git
from pathlib import Path
import json
from typing import List, Dict, Any

# =============================================================================
# WORKING DIRECTORY SETUP
# =============================================================================

def get_working_directory():
    """Get working directory from command line argument or current directory"""
    if len(sys.argv) > 1:
        working_dir = os.path.abspath(sys.argv[1])
    else:
        working_dir = os.getcwd()
    
    # Validate directory exists
    if not os.path.exists(working_dir):
        # print(f"❌ Error: Directory {working_dir} does not exist")
        sys.exit(1)
    
    if not os.path.isdir(working_dir):
        # print(f"❌ Error: {working_dir} is not a directory")
        sys.exit(1)
    
    return working_dir

# Get the working directory - THIS IS THE SINGLE SOURCE OF TRUTH
WORKING_DIR = get_working_directory()

# print(f"🚀 MCP Server starting for directory: {WORKING_DIR}")
# print(f"📁 Directory basename: {os.path.basename(WORKING_DIR)}")

# Initialize MCP server with dynamic name
mcp = FastMCP(f"Codebase Manager - {os.path.basename(WORKING_DIR)}")

def validate_path(file_path: str) -> str:
    """Validate and resolve file path within working directory"""
    abs_path = os.path.abspath(os.path.join(WORKING_DIR, file_path))
    if not abs_path.startswith(WORKING_DIR):
        raise ValueError("Access denied: Path outside working directory")
    return abs_path

# =============================================================================
# FILE SYSTEM OPERATIONS
# =============================================================================

@mcp.tool()
def read_file(file_path: str) -> str:
    """Read contents of a file in the working directory"""
    try:
        abs_path = validate_path(file_path)
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"📄 File: {file_path}\n{'='*50}\n{content}"
    except Exception as e:
        return f"❌ Error reading file {file_path}: {str(e)}"

@mcp.tool()
def write_file(file_path: str, content: str) -> str:
    """Write content to a file"""
    try:
        abs_path = validate_path(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ Successfully wrote to {file_path}"
    except Exception as e:
        return f"❌ Error writing file {file_path}: {str(e)}"

@mcp.tool()
def create_file(file_path: str, content: str = "") -> str:
    """Create a new file with optional initial content"""
    try:
        abs_path = validate_path(file_path)
        if os.path.exists(abs_path):
            return f"❌ File already exists: {file_path}"
        
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"✅ Created new file: {file_path}"
    except Exception as e:
        return f"❌ Error creating file {file_path}: {str(e)}"

@mcp.tool()
def delete_file(file_path: str) -> str:
    """Delete a file"""
    try:
        abs_path = validate_path(file_path)
        if not os.path.exists(abs_path):
            return f"❌ File does not exist: {file_path}"
        
        os.remove(abs_path)
        return f"✅ Deleted file: {file_path}"
    except Exception as e:
        return f"❌ Error deleting file {file_path}: {str(e)}"

@mcp.tool()
def list_directory(dir_path: str = ".") -> str:
    """List files and directories with details"""
    try:
        abs_path = validate_path(dir_path)
        items = []
        total_size = 0
        
        for item in sorted(os.listdir(abs_path)):
            item_path = os.path.join(abs_path, item)
            if os.path.isdir(item_path):
                items.append(f"📁 {item}/")
            else:
                size = os.path.getsize(item_path)
                total_size += size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024*1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size/(1024*1024):.1f} MB"
                items.append(f"📄 {item} ({size_str})")
        
        result = f"📁 Directory: {dir_path}\n"
        result += f"📊 Total files: {len([i for i in items if i.startswith('📄')])}, "
        result += f"Total directories: {len([i for i in items if i.startswith('📁')])}\n"
        if total_size > 0:
            if total_size < 1024*1024:
                result += f"💾 Total size: {total_size/1024:.1f} KB\n"
            else:
                result += f"💾 Total size: {total_size/(1024*1024):.1f} MB\n"
        result += "-" * 50 + "\n"
        result += "\n".join(items)
        
        return result
    except Exception as e:
        return f"❌ Error listing directory {dir_path}: {str(e)}"

@mcp.tool()
def search_files(pattern: str, file_extension: str = None, include_content: bool = False) -> str:
    """Search for files by pattern and optionally search content"""
    import glob
    
    try:
        search_pattern = f"**/*{pattern}*"
        if file_extension:
            search_pattern += f".{file_extension}"
        
        files = glob.glob(search_pattern, recursive=True, root_dir=WORKING_DIR)
        results = []
        
        for file in files[:20]:  # Limit results
            file_info = f"📄 {file}"
            
            if include_content:
                try:
                    file_path = os.path.join(WORKING_DIR, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if pattern.lower() in content.lower():
                            # Find lines containing the pattern
                            matching_lines = []
                            for i, line in enumerate(content.split('\n')):
                                if pattern.lower() in line.lower():
                                    matching_lines.append(f"    Line {i+1}: {line.strip()}")
                                if len(matching_lines) >= 3:  # Limit to 3 matches per file
                                    break
                            if matching_lines:
                                file_info += "\n" + "\n".join(matching_lines)
                except:
                    pass
            
            results.append(file_info)
        
        if not results:
            return f"❌ No files found matching '{pattern}'"
        
        return f"🔍 Found {len(results)} files matching '{pattern}':\n" + "\n\n".join(results)
    except Exception as e:
        return f"❌ Error searching files: {str(e)}"

# =============================================================================
# GIT OPERATIONS
# =============================================================================

@mcp.tool()
def git_status() -> str:
    """Get comprehensive Git repository status"""
    try:
        repo = git.Repo(WORKING_DIR)
        
        status_info = []
        status_info.append(f"🌿 Current branch: {repo.active_branch.name}")
        
        # Modified files
        modified = [item.a_path for item in repo.index.diff(None)]
        if modified:
            status_info.append(f"\n📝 Modified files ({len(modified)}):")
            for file in modified:
                status_info.append(f"  • {file}")
        
        # Staged files
        staged = [item.a_path for item in repo.index.diff("HEAD")]
        if staged:
            status_info.append(f"\n✅ Staged files ({len(staged)}):")
            for file in staged:
                status_info.append(f"  • {file}")
        
        # Untracked files
        if repo.untracked_files:
            status_info.append(f"\n❓ Untracked files ({len(repo.untracked_files)}):")
            for file in repo.untracked_files[:10]:  # Limit to 10
                status_info.append(f"  • {file}")
        
        # Check if ahead/behind remote
        try:
            current_branch = repo.active_branch.name
            remote_branch = f"origin/{current_branch}"
            if remote_branch in [ref.name for ref in repo.refs]:
                ahead = list(repo.iter_commits(f'{remote_branch}..HEAD'))
                behind = list(repo.iter_commits(f'HEAD..{remote_branch}'))
                if ahead:
                    status_info.append(f"\n⬆️  Ahead by {len(ahead)} commits")
                if behind:
                    status_info.append(f"\n⬇️  Behind by {len(behind)} commits")
        except:
            pass
        
        return "\n".join(status_info)
    except git.exc.InvalidGitRepositoryError:
        return f"❌ Not a git repository: {WORKING_DIR}"
    except Exception as e:
        return f"❌ Error getting git status: {str(e)}"

@mcp.tool()
def git_add(files: List[str]) -> str:
    """Stage files for commit"""
    try:
        repo = git.Repo(WORKING_DIR)
        
        # Validate all files exist first
        for file in files:
            file_path = os.path.join(WORKING_DIR, file)
            if not os.path.exists(file_path):
                return f"❌ File does not exist: {file}"
        
        repo.index.add(files)
        return f"✅ Successfully staged {len(files)} files:\n" + "\n".join(f"  • {f}" for f in files)
    except git.exc.InvalidGitRepositoryError:
        return f"❌ Not a git repository: {WORKING_DIR}"
    except Exception as e:
        return f"❌ Error staging files: {str(e)}"

@mcp.tool()
def git_commit(message: str, add_all: bool = False) -> str:
    """Create a commit with the given message"""
    try:
        repo = git.Repo(WORKING_DIR)
        
        if add_all:
            # Add all modified files
            repo.git.add(A=True)
        
        # Check if there are changes to commit
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            return "❌ No changes to commit"
        
        commit = repo.index.commit(message)
        return f"✅ Committed: {commit.hexsha[:8]} - {message}"
    except git.exc.InvalidGitRepositoryError:
        return f"❌ Not a git repository: {WORKING_DIR}"
    except Exception as e:
        return f"❌ Error committing: {str(e)}"

@mcp.tool()
def git_branch_operations(action: str, branch_name: str = None) -> str:
    """Git branch operations: list, create, switch, delete"""
    try:
        repo = git.Repo(WORKING_DIR)
        
        if action == "list":
            branches = []
            current_branch = repo.active_branch.name
            for branch in repo.branches:
                marker = "* " if branch.name == current_branch else "  "
                branches.append(f"{marker}{branch.name}")
            return "🌿 Branches:\n" + "\n".join(branches)
        
        elif action == "create":
            if not branch_name:
                return "❌ Branch name required for create action"
            new_branch = repo.create_head(branch_name)
            return f"✅ Created branch: {branch_name}"
        
        elif action == "switch":
            if not branch_name:
                return "❌ Branch name required for switch action"
            repo.git.checkout(branch_name)
            return f"✅ Switched to branch: {branch_name}"
        
        elif action == "delete":
            if not branch_name:
                return "❌ Branch name required for delete action"
            repo.delete_head(branch_name)
            return f"✅ Deleted branch: {branch_name}"
        
        else:
            return "❌ Invalid action. Use: list, create, switch, delete"
            
    except git.exc.InvalidGitRepositoryError:
        return f"❌ Not a git repository: {WORKING_DIR}"
    except Exception as e:
        return f"❌ Error with branch operation: {str(e)}"

@mcp.tool()
def git_diff(file_path: str = None, staged: bool = False) -> str:
    """Show git diff for files"""
    try:
        repo = git.Repo(WORKING_DIR)
        
        if staged:
            diff = repo.git.diff('--cached', file_path) if file_path else repo.git.diff('--cached')
            title = f"Staged changes" + (f" for {file_path}" if file_path else "")
        else:
            diff = repo.git.diff(file_path) if file_path else repo.git.diff()
            title = f"Working directory changes" + (f" for {file_path}" if file_path else "")
        
        if not diff:
            return f"No {title.lower()}"
        
        return f"📊 {title}:\n{'='*50}\n{diff}"
    except git.exc.InvalidGitRepositoryError:
        return f"❌ Not a git repository: {WORKING_DIR}"
    except Exception as e:
        return f"❌ Error getting diff: {str(e)}"

@mcp.tool()
def git_log(max_count: int = 10, file_path: str = None) -> str:
    """Get commit history"""
    try:
        repo = git.Repo(WORKING_DIR)
        commits = []
        
        commit_iter = repo.iter_commits(max_count=max_count, paths=file_path if file_path else None)
        
        for commit in commit_iter:
            commits.append(
                f"🔸 {commit.hexsha[:8]} - {commit.message.strip()}\n"
                f"   👤 {commit.author} | 📅 {commit.committed_datetime.strftime('%Y-%m-%d %H:%M')}"
            )
        
        title = f"Last {len(commits)} commits" + (f" for {file_path}" if file_path else "")
        return f"📜 {title}:\n" + "\n\n".join(commits)
    except git.exc.InvalidGitRepositoryError:
        return f"❌ Not a git repository: {WORKING_DIR}"
    except Exception as e:
        return f"❌ Error getting git log: {str(e)}"

# =============================================================================
# COMMAND EXECUTION
# =============================================================================


@mcp.tool()
def execute_command(command: str, args: List[str] = None, timeout: int = 60) -> str:
    ALLOWED_COMMANDS = {
        'python', 'python3', 'pip', 'pip3',
        'node', 'npm', 'yarn', 'pnpm',
        'pytest', 'black', 'flake8', 'mypy', 'isort',
        'git', 'ls', 'dir', 'pwd', 'whoami',
        'cat', 'head', 'tail', 'grep',
        'cargo', 'rustc', 'go', 'javac', 'java',
        'make', 'cmake', 'docker', 'docker-compose'
    }

    if command not in ALLOWED_COMMANDS:
        return f"❌ Command '{command}' not allowed."

    cmd = [command] + (args or [])
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=WORKING_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Timeout handler
        timer = threading.Timer(timeout, proc.kill)
        timer.start()

        stdout, stderr = proc.communicate()
        timer.cancel()

        output = [
            f"💻 Command: {' '.join(cmd)}",
            f"📁 Working directory: {WORKING_DIR}",
            f"🔢 Exit code: {proc.returncode}"
        ]

        if stdout:
            output.append(f"\n📤 STDOUT:\n{stdout}")
        if stderr:
            output.append(f"\n❌ STDERR:\n{stderr}")

        return "\n".join(output)

    except Exception as e:
        return f"❌ Error executing command: {str(e)}"

@mcp.tool()
def run_tests(test_command: str = "pytest", test_path: str = "tests/") -> str:
    """Run tests in the project"""
    return execute_command(test_command, [test_path, "-v"])

# =============================================================================
# PROJECT RESOURCES
# =============================================================================

@mcp.resource("project://info")
def get_project_info() -> str:
    """Get basic project information"""
    info = []
    info.append(f"📁 Project Directory: {WORKING_DIR}")
    
    # Calculate directory size
    total_size = sum(
        os.path.getsize(os.path.join(dirpath, filename))
        for dirpath, dirnames, filenames in os.walk(WORKING_DIR)
        for filename in filenames
    )
    info.append(f"💾 Directory Size: {total_size / (1024*1024):.1f} MB")
    
    # Check for common project files
    common_files = [
        "README.md", "requirements.txt", "pyproject.toml", "setup.py",
        "package.json", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
        ".gitignore", "Dockerfile", "docker-compose.yml"
    ]
    
    found_files = []
    for file in common_files:
        if os.path.exists(os.path.join(WORKING_DIR, file)):
            found_files.append(file)
    
    if found_files:
        info.append(f"📋 Found project files: {', '.join(found_files)}")
    
    # Git info
    try:
        repo = git.Repo(WORKING_DIR)
        info.append(f"🌿 Git branch: {repo.active_branch.name}")
        info.append(f"📝 Last commit: {repo.head.commit.hexsha[:8]} - {repo.head.commit.message.strip()}")
    except:
        info.append("❌ Not a git repository")
    
    return "\n".join(info)

@mcp.resource("project://structure")
def get_project_structure() -> str:
    """Get project directory structure"""
    def build_tree(path, prefix="", max_depth=3, current_depth=0):
        if current_depth >= max_depth:
            return ""
        
        try:
            items = sorted([item for item in os.listdir(path) if not item.startswith('.')])
        except PermissionError:
            return f"{prefix}❌ Permission denied\n"
        
        tree = ""
        for i, item in enumerate(items):
            # Skip common build/cache directories
            if item in ['.git', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build']:
                continue
                
            item_path = os.path.join(path, item)
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            
            if os.path.isdir(item_path):
                tree += f"{prefix}{current_prefix}📁 {item}/\n"
                if current_depth < max_depth - 1:
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    tree += build_tree(item_path, next_prefix, max_depth, current_depth + 1)
            else:
                tree += f"{prefix}{current_prefix}📄 {item}\n"
        
        return tree
    
    return f"📁 {os.path.basename(WORKING_DIR)}/\n" + build_tree(WORKING_DIR)

@mcp.resource("project://dependencies")
def get_dependencies() -> str:
    """Get project dependencies from various files"""
    dep_files = {
        "requirements.txt": "Python pip requirements",
        "pyproject.toml": "Python project configuration",
        "package.json": "Node.js dependencies",
        "Cargo.toml": "Rust dependencies",
        "go.mod": "Go module dependencies",
        "pom.xml": "Java Maven dependencies",
        "build.gradle": "Java Gradle dependencies"
    }
    
    found_deps = []
    
    for dep_file, description in dep_files.items():
        file_path = os.path.join(WORKING_DIR, dep_file)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                found_deps.append(f"📋 {description} ({dep_file}):\n{'-'*50}\n{content}\n")
            except Exception as e:
                found_deps.append(f"❌ Error reading {dep_file}: {str(e)}\n")
    
    return "\n".join(found_deps) if found_deps else "❌ No dependency files found"

# =============================================================================
# SERVER STARTUP
# =============================================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")