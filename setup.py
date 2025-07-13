#!/usr/bin/env python3
"""
Setup script for Codebase MCP Server
This script helps you configure Claude Desktop to use the codebase server
"""

import os
import json
import sys
import shutil
from pathlib import Path

def get_claude_config_path():
    """Get the Claude Desktop configuration file path based on OS"""
    if sys.platform == "darwin":  # macOS
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    elif sys.platform == "win32":  # Windows
        return Path(os.environ["APPDATA"]) / "Claude/claude_desktop_config.json"
    else:  # Linux
        return Path.home() / ".config/claude/claude_desktop_config.json"

def get_server_path():
    """Get the absolute path to the codebase server"""
    script_dir = Path(__file__).parent.absolute()
    server_path = script_dir / "codebase_server.py"
    
    if not server_path.exists():
        print(f"❌ Server file not found at: {server_path}")
        print("Please make sure codebase_server.py is in the same directory as this setup script")
        return None
    
    return str(server_path)

def get_python_path():
    """Get the Python executable path"""
    python_path = shutil.which("python3") or shutil.which("python")
    if not python_path:
        print("❌ Python not found in PATH")
        return None
    return python_path

def create_claude_config(server_path, python_path):
    """Create or update Claude Desktop configuration"""
    config_path = get_claude_config_path()
    
    # Create directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing config or create new one
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            print("⚠️  Invalid JSON in existing config, creating new one")
            config = {}
    else:
        config = {}
    
    # Ensure mcpServers exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Add our server configurations
    config["mcpServers"]["codebase-manager"] = {
        "command": python_path,
        "args": [server_path],
        "env": {}
    }
    
    # Save the configuration
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Configuration saved to: {config_path}")
    return config_path

def create_project_launcher():
    """Create a script to easily launch the server for any project"""
    script_content = f'''#!/usr/bin/env python3
"""
Project-specific Codebase MCP Server launcher
Usage: python launch_for_project.py [project_directory]
"""
import sys
import subprocess
import os

def main():
    server_path = "{get_server_path()}"
    python_path = "{get_python_path()}"
    
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = os.getcwd()
    
    print(f"🚀 Starting Codebase MCP Server for: {{project_dir}}")
    
    try:
        subprocess.run([python_path, server_path, project_dir])
    except KeyboardInterrupt:
        print("\\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Error: {{e}}")

if __name__ == "__main__":
    main()
'''
    
    launcher_path = Path(__file__).parent / "launch_for_project.py"
    with open(launcher_path, 'w') as f:
        f.write(script_content)
    
    # Make it executable on Unix systems
    if sys.platform != "win32":
        os.chmod(launcher_path, 0o755)
    
    print(f"✅ Project launcher created: {launcher_path}")
    return launcher_path

def create_vscode_config():
    """Create VS Code configuration for easy switching"""
    vscode_config = {
        "mcp": {
            "servers": {
                "codebase-manager": {
                    "command": get_python_path(),
                    "args": [get_server_path(), "${workspaceFolder}"]
                }
            }
        }
    }
    
    vscode_dir = Path.cwd() / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    
    config_path = vscode_dir / "mcp.json"
    with open(config_path, 'w') as f:
        json.dump(vscode_config, f, indent=2)
    
    print(f"✅ VS Code MCP config created: {config_path}")
    return config_path

def main():
    print("🔧 Codebase MCP Server Setup")
    print("=" * 40)
    
    # Check if server file exists
    server_path = get_server_path()
    if not server_path:
        return
    
    # Check if Python is available
    python_path = get_python_path()
    if not python_path:
        return
    
    print(f"📁 Server path: {server_path}")
    print(f"🐍 Python path: {python_path}")
    
    # Create Claude Desktop configuration
    try:
        config_path = create_claude_config(server_path, python_path)
        print(f"✅ Claude Desktop configured")
    except Exception as e:
        print(f"❌ Error configuring Claude Desktop: {e}")
        return
    
    # Create project launcher
    try:
        launcher_path = create_project_launcher()
    except Exception as e:
        print(f"⚠️  Could not create project launcher: {e}")
    
    # Create VS Code config
    try:
        create_vscode_config()
    except Exception as e:
        print(f"⚠️  Could not create VS Code config: {e}")
    
    print("\n" + "=" * 40)
    print("🎉 Setup complete!")
    print("\nNext steps:")
    print("1. Restart Claude Desktop")
    print("2. In Claude, you should now see the codebase-manager tools")
    print("3. Use commands like 'list the files in my project' or 'show me git status'")
    print("\nFor different projects:")
    print(f"- Edit {config_path}")
    print("- Change the args to point to your project directory")
    print("- Or use the project launcher script")

if __name__ == "__main__":
    main()