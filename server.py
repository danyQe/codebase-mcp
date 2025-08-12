from site import abs_paths
from mcp.server.fastmcp import FastMCP, Context
import os
import sys
import subprocess
import threading
from typing import List, Dict, Any, Optional, Tuple
import git
from pathlib import Path
import json
import re
import shutil
import zipfile
import hashlib
import time
import fnmatch

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
        # exit with non-zero so agent notices
        sys.exit(1)

    if not os.path.isdir(working_dir):
        sys.exit(1)

    return os.path.abspath(working_dir)

# THIS IS THE SINGLE SOURCE OF TRUTH
WORKING_DIR = get_working_directory()

mcp = FastMCP(f"Codebase Manager - {os.path.basename(WORKING_DIR)}")

# =============================================================================
# GITIGNORE / IGNORE HELPERS
# =============================================================================

def load_gitignore_patterns(root_path: Optional[str] = None) -> List[str]:
    """
    Load ignore patterns from a .gitignore file in the given root_path.
    Returns a list of patterns. If no .gitignore found, returns empty list.
    Patterns are returned as-is to be used with fnmatch against relative paths.
    """
    if root_path is None:
        root_path = WORKING_DIR
    abs_root = os.path.abspath(root_path)
    gitignore_path = os.path.join(abs_root, ".gitignore")
    patterns: List[str] = []
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    return patterns


def should_ignore(path: str, patterns: List[str], root_path: Optional[str] = None) -> bool:
    """
    Check if a given file/folder should be ignored based on patterns.
    path must be absolute or relative; function will compare path relative to root_path.
    """
    if root_path is None:
        root_path = WORKING_DIR
    abs_root = os.path.abspath(root_path)
    abs_path = os.path.abspath(path)
    try:
        rel_path = os.path.relpath(abs_path, abs_root)
    except Exception:
        rel_path = os.path.basename(abs_path)

    # Normalize to use forward slashes for pattern matching
    rel_path_norm = rel_path.replace(os.path.sep, '/')

    for pattern in patterns:
        # also normalize pattern
        pattern_norm = pattern.replace(os.path.sep, '/')
        # if pattern ends with '/', ensure it matches directories
        if pattern_norm.endswith('/'):
            # match prefix
            if rel_path_norm.startswith(pattern_norm.rstrip('/')):
                return True
        if fnmatch.fnmatch(rel_path_norm, pattern_norm) or fnmatch.fnmatch(os.path.basename(rel_path_norm), pattern_norm):
            return True
    return False

# Add some always-ignore defaults on top of .gitignore
DEFAULT_IGNORE = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '*.pyc', '*.pyo'
}


# =============================================================================
# UTILITIES
# =============================================================================

def validate_path(file_path: str) -> str:
    """Validate and resolve file path within working directory"""
    if os.path.isabs(file_path):
        abs_path = os.path.abspath(file_path)
    else:
        abs_path = os.path.abspath(os.path.join(WORKING_DIR, file_path))

    # Normalize trailing separators
    abs_path = os.path.normpath(abs_path)

    # Ensure the path is inside WORKING_DIR
    work_norm = os.path.normpath(WORKING_DIR)
    if not abs_path.startswith(work_norm):
        raise ValueError("Access denied: Path outside working directory")
    return abs_path


def is_binary_file(path: str) -> bool:
    """Heuristic to skip binary files when reading text: read first bytes and check for nulls"""
    try:
        with open(path, 'rb') as f:
            chunk = f.read(2048)
            if b'\0' in chunk:
                return True
            # high ratio of non-text bytes
            text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
            if not chunk:
                return False
            nontext = sum(1 for b in chunk if b not in text_chars)
            return (nontext / len(chunk)) > 0.30
    except Exception:
        return True


def safe_read_text(path: str, max_chars: Optional[int] = None) -> str:
    """Read text from file safely, optionally truncated to max_chars."""
    if is_binary_file(path):
        return ""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            if max_chars:
                return f.read(max_chars)
            return f.read()
    except Exception:
        return ""


def short_hash(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:8]


# =============================================================================
# MCP FILE SYSTEM OPERATIONS
# =============================================================================

@mcp.tool()
def read_file(file_path: str, with_line_numbers: bool = False, max_chars: Optional[int] = None) -> str:
    """Read contents of a file in the working directory.

    If with_line_numbers=True, prepend line numbers to each line.
    max_chars: if provided, truncate the returned content to approximately that many characters.
    """
    try:
        abs_path = validate_path(file_path)
        if not os.path.exists(abs_path):
            return f"❌ Error: File not found: {file_path}"
        if os.path.isdir(abs_path):
            return f"❌ Error: Path is a directory: {file_path}"
        if is_binary_file(abs_path):
            return f"❌ Error: Binary file: {file_path}"

        lines = []
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                lines.append(line.rstrip('\n'))

        if with_line_numbers:
            width = len(str(len(lines)))
            numbered = [f"{str(i+1).rjust(width)} | {line}" for i, line in enumerate(lines)]
            out = "\n".join(numbered)
        else:
            out = "\n".join(lines)

        if max_chars and len(out) > max_chars:
            out = out[:max_chars] + "\n... (truncated)"

        return f"📄 File: {file_path}\n{'='*50}\n" + out
    except Exception as e:
        return f"❌ Error reading file {file_path}: {str(e)}"


@mcp.tool()
def get_project_tree_structure(root_path: str = ".", max_depth: Optional[int] = None) -> str:
    """
    Returns a string representing the full tree structure of the given directory,
    ignoring files/folders from .gitignore and some defaults.
    """
    try:
        abs_root = validate_path(root_path)
    except Exception as e:
        return f"❌ Error: {e}"

    patterns = load_gitignore_patterns(WORKING_DIR)  # ensure patterns loaded from project root
    tree_lines: List[str] = []

    def walk(dir_path: str, prefix: str = "", depth: int = 0):
        if max_depth is not None and depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            tree_lines.append(f"{prefix} [Permission Denied]")
            return

        # Filter out ignored and default ignored paths
        filtered = []
        for e in entries:
            full = os.path.join(dir_path, e)
            if e in DEFAULT_IGNORE:
                continue
            if should_ignore(full, patterns, WORKING_DIR):
                continue
            filtered.append(e)

        for idx, entry in enumerate(filtered):
            path = os.path.join(dir_path, entry)
            connector = "└── " if idx == len(filtered) - 1 else "├── "
            tree_lines.append(f"{prefix}{connector}{entry}")
            if os.path.isdir(path):
                extension = "    " if idx == len(filtered) - 1 else "│   "
                walk(path, prefix + extension, depth + 1)

    tree_lines.append(os.path.basename(abs_root) or abs_root)
    walk(abs_root)
    return "\n".join(tree_lines)


@mcp.tool()
def get_file_preview(file_path: str, lines_head: int = 20, lines_tail: int = 0, bytes_max: int = 0, with_line_numbers: bool = False) -> str:
    """
    Preview a file safely with options for head/tail lines and optional line numbers.
    """
    try:
        abs_path = validate_path(file_path)
        if not os.path.exists(abs_path):
            return f"❌ File not found: {file_path}"
        if is_binary_file(abs_path):
            return f"❌ Binary file preview not supported: {file_path}"

        head_lines = []
        tail_lines = []
        if lines_head > 0:
            with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
                for _ in range(lines_head):
                    line = f.readline()
                    if not line:
                        break
                    head_lines.append(line.rstrip('\n'))

        if lines_tail > 0:
            with open(abs_path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                end = f.tell()
                size = 4096
                data = bytearray()
                while end > 0 and len(tail_lines) < lines_tail:
                    read_size = min(size, end)
                    f.seek(end - read_size)
                    chunk = f.read(read_size)
                    data = chunk + data
                    lines = data.splitlines()
                    if len(lines) > lines_tail + 1:
                        break
                    end -= read_size
                try:
                    text = data.decode('utf-8', errors='replace')
                except Exception:
                    text = data.decode('latin-1', errors='replace')
                tail_lines = text.splitlines()[-lines_tail:]

        combined = []
        if head_lines:
            combined.append("-- HEAD --")
            combined.extend(head_lines)
        if lines_tail > 0 and tail_lines:
            if head_lines and lines_tail:
                combined.append("... (skipped middle) ...")
            combined.append("-- TAIL --")
            combined.extend(tail_lines)

        out = "\n".join(combined)
        if with_line_numbers and out:
            # naive line numbering for preview
            lines = out.splitlines()
            width = len(str(len(lines)))
            out = "\n".join([f"{str(i+1).rjust(width)} | {l}" for i, l in enumerate(lines)])

        if bytes_max and len(out.encode('utf-8')) > bytes_max:
            out = out.encode('utf-8')[:bytes_max].decode('utf-8', errors='replace')
            out += "\n... (truncated to bytes_max)"
        return f"📄 Preview: {file_path}\n{'='*40}\n{out}"
    except Exception as e:
        return f"❌ Error getting preview for {file_path}: {str(e)}"


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


# =============================================================================
# ADVANCED SEARCH & INDEXING
# =============================================================================

def rg_available() -> bool:
    """Check if ripgrep (rg) is available on PATH"""
    try:
        if os.name == 'nt':
            proc = subprocess.run(['where', 'rg'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        else:
            proc = subprocess.run(['which', 'rg'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except Exception:
        return False


@mcp.tool()
def search_code(pattern: str,
                file_glob: Optional[str] = None,
                ignore_case: bool = True,
                regex: bool = True,
                max_results: int = 100,
                include_context_lines: int = 0) -> str:
    """
    Search code across repository. Uses ripgrep (rg) if available, otherwise falls back to python scanning.
    """
    try:
        if rg_available():
            cmd = ['rg', '--hidden', '--line-number', '--no-ignore-vcs']
            if ignore_case:
                cmd.append('-i')
            if not regex:
                cmd.append('--fixed-strings')
            if include_context_lines and isinstance(include_context_lines, int):
                cmd.extend(['-C', str(include_context_lines)])
            if file_glob:
                cmd.extend(['--glob', file_glob])
            cmd.append(pattern)
            proc = subprocess.run(cmd, cwd=WORKING_DIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out = proc.stdout.strip()
            if not out:
                return f"❌ No matches found for '{pattern}'"
            lines = out.splitlines()[:max_results]
            return "🔍 ripgrep results:\n" + "\n".join(lines)
        else:
            flags = re.IGNORECASE if ignore_case else 0
            compiled = re.compile(pattern, flags) if regex else re.compile(re.escape(pattern), flags)
            matches = []
            for root, _, files in os.walk(WORKING_DIR):
                if any(x in root for x in (os.path.join(WORKING_DIR, '.git'), 'node_modules', '__pycache__')):
                    continue
                for fname in files:
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, WORKING_DIR)
                    if file_glob and not Path(rel).match(file_glob):
                        continue
                    try:
                        if is_binary_file(fpath):
                            continue
                        with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                            for idx, line in enumerate(fh, start=1):
                                if compiled.search(line):
                                    context = ''
                                    if include_context_lines:
                                        fh.seek(0)
                                        all_lines = fh.read().splitlines()
                                        start = max(0, idx - 1 - include_context_lines)
                                        end = min(len(all_lines), idx - 1 + include_context_lines + 1)
                                        context = "\n".join(all_lines[start:end])
                                    matches.append(f"{rel}:{idx}: {line.strip()}" + (f"\n---context---\n{context}" if context else ""))
                                    break
                    except Exception:
                        continue
                    if len(matches) >= max_results:
                        break
                if len(matches) >= max_results:
                    break
            if not matches:
                return f"❌ No matches found for '{pattern}'"
            return f"🔍 Python search results ({len(matches)}):\n" + "\n\n".join(matches)
    except Exception as e:
        return f"❌ Error searching code: {str(e)}"

INDEX_FILENAME = os.path.join(WORKING_DIR, '.mcp_index.json')

# =============================================================================
# CODE SYMBOL INDEXER (functions/classes for py, js, ts, tsx, jsx, html)
# =============================================================================

# simple language inference from extension
EXT_LANG = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.html': 'html',
}

# patterns to detect symbol declarations - tuned for common cases (not full parsers)
SYMBOL_PATTERNS = {
    'python': [
        (re.compile(r'^\s*def\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
        (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(:|\(|$)'), 'class'),
    ],
    'javascript': [
        (re.compile(r'^\s*function\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
        (re.compile(r'^\s*(?:const|let|var)\s+([a-zA-Z_][\w_]*)\s*=\s*\('), 'function'),
        (re.compile(r'^\s*([a-zA-Z_][\w_]*)\s*:\s*function\s*\('), 'function'),
        (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(?:\{|extends|$)'), 'class'),
        # arrow functions: const foo = (...) =>
        (re.compile(r'^\s*(?:const|let|var)\s+([a-zA-Z_][\w_]*)\s*=\s*\([^)]*\)\s*=>'), 'function'),
    ],
    'typescript': [
        (re.compile(r'^\s*function\s+([a-zA-Z_][\w_]*)\s*\('), 'function'),
        (re.compile(r'^\s*(?:const|let|var)\s+([a-zA-Z_][\w_]*)\s*=\s*\([^)]*\)\s*=>'), 'function'),
        (re.compile(r'^\s*class\s+([a-zA-Z_][\w_]*)\s*(?:\{|extends|$)'), 'class'),
        (re.compile(r'^\s*(?:export\s+default\s+function)\s+([a-zA-Z_][\w_]*)'), 'function'),
    ],
    'html': [
        # look for custom elements or script embedded functions? We'll ignore html for deep parsing,
        # but allow detection of <script> tags boundaries as symbols for manual inspection.
    ]
}


def detect_language_from_path(path: str) -> str:
    _, ext = os.path.splitext(path)
    return EXT_LANG.get(ext.lower(), 'text')


def build_code_index(force: bool = False, max_files: int = 20000) -> str:
    """
    Walks the project and builds a simple index mapping symbol name -> locations.
    Each location includes: file (relative), line (1-based), kind (function/class), lang
    """
    try:
        if os.path.exists(INDEX_FILENAME) and not force:
            return f"❗ Index already exists at .mcp_index.json. Use force=True to rebuild."

        patterns = load_gitignore_patterns(WORKING_DIR)
        index: Dict[str, List[Dict[str, Any]]] = {}
        count = 0
        for root, _, files in os.walk(WORKING_DIR):
            # skip default ignores early
            if any(skip in root for skip in (os.path.join(WORKING_DIR, '.git'), 'node_modules', '__pycache__')):
                continue
            for fname in files:
                if count >= max_files:
                    break
                rel = os.path.relpath(os.path.join(root, fname), WORKING_DIR)
                # skip by gitignore
                if should_ignore(os.path.join(root, fname), patterns, WORKING_DIR):
                    continue
                lang = detect_language_from_path(fname)
                if lang == 'text' and not fname.endswith(('.html',)):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    if is_binary_file(fpath):
                        continue
                    with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                        for i, line in enumerate(fh, start=1):
                            if lang in SYMBOL_PATTERNS:
                                for pat, kind in SYMBOL_PATTERNS[lang]:
                                    m = pat.match(line)
                                    if m:
                                        name = m.group(1)
                                        entry = {"file": rel, "line": i, "kind": kind, "lang": lang}
                                        index.setdefault(name, []).append(entry)
                            else:
                                # optionally detect simple "class=" in html? skip for now
                                pass
                except Exception:
                    continue
                count += 1
            if count >= max_files:
                break

        data = {"generated": time.time(), "root": WORKING_DIR, "symbols": index}
        with open(INDEX_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return f"✅ Built symbol index with {sum(len(v) for v in index.values())} symbols -> .mcp_index.json"
    except Exception as e:
        return f"❌ Error building code index: {str(e)}"


@mcp.tool()
def read_index(limit: int = 50, symbol_filter: Optional[str] = None) -> str:
    """Read the generated symbol index and present summary"""
    try:
        if not os.path.exists(INDEX_FILENAME):
            return "❌ Index not found. Run build_code_index() first."
        with open(INDEX_FILENAME, 'r', encoding='utf-8') as f:
            data = json.load(f)
        symbols = data.get('symbols', {})
        if symbol_filter:
            symbols = {k: v for k, v in symbols.items() if symbol_filter in k}
        out_lines = []
        for name in sorted(symbols.keys())[:limit]:
            locs = symbols[name]
            out_lines.append(f"• {name} ({len(locs)} occurrences)")
            for loc in locs[:5]:
                out_lines.append(f"    - {loc['file']}:{loc['line']} ({loc['kind']})")
        return f"📦 Symbol Index summary ({len(symbols)} symbols total):\n" + "\n".join(out_lines)
    except Exception as e:
        return f"❌ Error reading index: {str(e)}"


# =============================================================================
# SYMBOL BOUNDS DETECTION & REPLACEMENT
# =============================================================================

def _leading_indent(s: str) -> int:
    return len(s) - len(s.lstrip(' '))


def find_symbol_bounds(lines: List[str], start_idx: int, kind: str, lang: str) -> Tuple[int, int]:
    """
    Given file lines (0-based list) and start_idx (0-based index where symbol declaration found),
    return (start_line, end_line) inclusive (0-based). Raises ValueError if cannot determine.
    """
    n = len(lines)
    if lang == 'python':
        # include decorators above
        s = start_idx
        while s - 1 >= 0 and lines[s-1].lstrip().startswith('@'):
            s -= 1
        base_indent = _leading_indent(lines[start_idx])
        end = start_idx
        for i in range(start_idx + 1, n):
            line = lines[i]
            if not line.strip():
                end = i
                continue
            indent = _leading_indent(line)
            # if indentation is less or equal than base and the line is not a continuation, we ended
            if indent <= base_indent and not line.lstrip().startswith('#'):
                # reached next top-level or sibling
                return s, i - 1
            end = i
        return s, n - 1
    else:
        # javascript/typescript/html: use brace matching starting from the first '{' after start_idx
        # if no '{' found, treat single-line as the definition
        brace_stack = []
        opened = False
        start_line = start_idx
        for i in range(start_idx, n):
            l = lines[i]
            if not opened:
                if '{' in l:
                    pos = l.find('{')
                    opened = True
                    brace_stack.append('{')
                    # check if there are more braces on line
                    brace_stack += ['{'] * (l.count('{') - 1)
                    # reduce for '}' on same line
                    for _ in range(l.count('}')):
                        if brace_stack:
                            brace_stack.pop()
                    if not brace_stack:
                        return start_line, i
                else:
                    # single-line arrow function or concise return like: const f = () => x;
                    if ';' in l or l.strip().endswith(')'):
                        return start_line, i
                    continue
            else:
                # opened, track braces
                for ch in l:
                    if ch == '{':
                        brace_stack.append('{')
                    elif ch == '}':
                        if brace_stack:
                            brace_stack.pop()
                if not brace_stack:
                    return start_line, i
        # fallback: return to EOF
        return start_line, n - 1


def _update_index_after_replace(symbol_name: str, file_rel: str, new_line: int) -> None:
    # best-effort: update index file positions for this symbol occurrence
    try:
        if not os.path.exists(INDEX_FILENAME):
            return
        with open(INDEX_FILENAME, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sym = data.get('symbols', {})
        if symbol_name in sym:
            for entry in sym[symbol_name]:
                if entry.get('file') == file_rel:
                    entry['line'] = new_line
        with open(INDEX_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


@mcp.tool()
def replace_symbol(file_path: str, symbol_name: str, new_code: str, occurrence: int = 1) -> str:
    """
    Replace the body of the symbol (function/class) in the given file.
    - file_path: relative to WORKING_DIR or absolute (validated)
    - symbol_name: name of the function/class
    - new_code: replacement code (string). It will replace the old symbol including signature line(s) through end.
    - occurrence: if multiple definitions with same name in file, choose which one (1-based)

    Returns status message.
    """
    try:
        abs_path = validate_path(file_path)
        rel = os.path.relpath(abs_path, WORKING_DIR)
        if not os.path.exists(abs_path):
            return f"❌ File not found: {file_path}"
        if is_binary_file(abs_path):
            return f"❌ Binary file: {file_path}"

        with open(abs_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()

        lang = detect_language_from_path(file_path)
        # find all declaration lines matching symbol_name
        decl_indices = []
        if lang in SYMBOL_PATTERNS:
            pats = SYMBOL_PATTERNS[lang]
            for i, line in enumerate(lines):
                for pat, kind in pats:
                    m = pat.match(line)
                    if m and m.group(1) == symbol_name:
                        decl_indices.append((i, kind))
        else:
            return f"❌ Unsupported language for replacement: {lang}"

        if not decl_indices:
            return f"❌ Symbol '{symbol_name}' not found in {file_path}"
        if occurrence < 1 or occurrence > len(decl_indices):
            return f"❌ Invalid occurrence: {occurrence}. Found {len(decl_indices)} occurrences."

        start_idx, kind = decl_indices[occurrence - 1]
        s, e = find_symbol_bounds(lines, start_idx, kind, lang)

        # prepare new code lines
        new_lines = new_code.splitlines()

        # ensure newline at end
        new_contents = lines[:s] + new_lines + lines[e+1:]

        # write back safely (atomic replace)
        backup = abs_path + ".bak"
        shutil.copyfile(abs_path, backup)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_contents) + '\n')

        # update index if present (best-effort)
        _update_index_after_replace(symbol_name, rel, s + 1)

        return f"✅ Replaced symbol '{symbol_name}' in {file_path} (lines {s+1}-{e+1}) -> new lines {s+1}-{s+len(new_lines)}"
    except Exception as e:
        return f"❌ Error replacing symbol: {str(e)}"


@mcp.tool()
def search_symbol(symbol: str, regex: bool = False, max_results: int = 100) -> str:
    """
    Search symbol name in the generated index (or live-scan if index missing).
    If regex=True, treat symbol as a regular expression and scan files.
    """
    try:
        if regex or not os.path.exists(INDEX_FILENAME):
            # fallback to code scan (simple search for symbol word)
            found = []
            pattern = re.compile(symbol) if regex else re.compile(r'\b' + re.escape(symbol) + r'\b')
            for root, _, files in os.walk(WORKING_DIR):
                if any(skip in root for skip in (os.path.join(WORKING_DIR, '.git'), 'node_modules', '__pycache__')):
                    continue
                for fname in files:
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, WORKING_DIR)
                    try:
                        if is_binary_file(fpath):
                            continue
                        with open(fpath, 'r', encoding='utf-8', errors='replace') as fh:
                            for i, line in enumerate(fh, start=1):
                                if pattern.search(line):
                                    found.append(f"{rel}:{i}: {line.strip()}")
                                    if len(found) >= max_results:
                                        break
                    except Exception:
                        continue
                if len(found) >= max_results:
                    break
            if not found:
                return f"❌ No matches for '{symbol}'"
            return f"🔎 Search results ({len(found)}):\n" + "\n".join(found)
        else:
            with open(INDEX_FILENAME, 'r', encoding='utf-8') as f:
                data = json.load(f)
            symbols = data.get('symbols', {})
            matches = {k: v for k, v in symbols.items() if symbol in k}
            if not matches:
                return f"❌ No symbols matching '{symbol}' in index"
            out = []
            for k, locs in matches.items():
                out.append(f"• {k} ({len(locs)} occurrences)")
                for loc in locs:
                    out.append(f"    - {loc['file']}:{loc['line']} ({loc['kind']})")
            return '\n'.join(out)
    except Exception as e:
        return f"❌ Error searching symbol: {str(e)}"


# =============================================================================
# REST OF ORIGINAL TOOLS (GIT, COMMAND EXECUTION, ZIP, RESOURCES)
# =============================================================================

@mcp.tool()
def git_status() -> str:
    try:
        repo = git.Repo(WORKING_DIR)
        status_info = []
        try:
            status_info.append(f"🌿 Current branch: {repo.active_branch.name}")
        except Exception:
            status_info.append("🌿 Current branch: (detached or unknown)")

        modified = [item.a_path for item in repo.index.diff(None)]
        if modified:
            status_info.append(f"\n📝 Modified files ({len(modified)}):")
            for file in modified:
                status_info.append(f"  • {file}")

        staged = [item.a_path for item in repo.index.diff("HEAD")]
        if staged:
            status_info.append(f"\n✅ Staged files ({len(staged)}):")
            for file in staged:
                status_info.append(f"  • {file}")

        if repo.untracked_files:
            status_info.append(f"\n❓ Untracked files ({len(repo.untracked_files)}):")
            for file in repo.untracked_files[:10]:
                status_info.append(f"  • {file}")

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
        except Exception:
            pass

        return "\n".join(status_info)
    except git.exc.InvalidGitRepositoryError:
        return f"❌ Not a git repository: {WORKING_DIR}"
    except Exception as e:
        return f"❌ Error getting git status: {str(e)}"


@mcp.tool()
def execute_command(command: str, args: List[str] = None, timeout: int = 60) -> str:
    ALLOWED_COMMANDS = {
        'python', 'python3', 'pip', 'pip3',
        'node', 'npm', 'yarn', 'pnpm',
        'pytest', 'black', 'flake8', 'mypy', 'isort',
        'git', 'ls', 'dir', 'pwd', 'whoami',
        'cat', 'head', 'tail', 'grep',
        'cargo', 'rustc', 'go', 'javac', 'java',
        'make', 'cmake', 'docker', 'docker-compose', 'rg'
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
            text=True,
            shell=False
        )

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
def zip_files(file_paths: List[str], out_name: str = "mcp_export.zip") -> str:
    try:
        abs_out = validate_path(out_name)
        os.makedirs(os.path.dirname(abs_out), exist_ok=True)
        with zipfile.ZipFile(abs_out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for rel in file_paths:
                abs_p = validate_path(rel)
                if not os.path.exists(abs_p):
                    return f"❌ File not found: {rel}"
                arcname = os.path.relpath(abs_p, WORKING_DIR)
                z.write(abs_p, arcname)
        return f"✅ Zipped {len(file_paths)} files -> {os.path.relpath(abs_out, WORKING_DIR)}"
    except Exception as e:
        return f"❌ Error zipping files: {str(e)}"


@mcp.resource("project://info")
def get_project_info() -> str:
    info = []
    info.append(f"📁 Project Directory: {WORKING_DIR}")

    total_size = 0
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(WORKING_DIR):
        if any(skip in dirpath for skip in ['.git', 'node_modules', 'dist', 'build', '__pycache__']):
            continue
        for filename in filenames:
            try:
                total_size += os.path.getsize(os.path.join(dirpath, filename))
                total_files += 1
            except Exception:
                continue
        if total_files > 50000:
            break

    info.append(f"💾 Approx Directory Size: {total_size / (1024*1024):.1f} MB")
    info.append(f"🗂️ Approx File Count: {total_files}")

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

    try:
        repo = git.Repo(WORKING_DIR)
        info.append(f"🌿 Git branch: {repo.active_branch.name}")
        info.append(f"📝 Last commit: {repo.head.commit.hexsha[:8]} - {repo.head.commit.message.strip()}")
    except Exception:
        info.append("❌ Not a git repository")

    info.append(f"🔎 ripgrep available: {'yes' if rg_available() else 'no'}")
    info.append(f"📦 Index present: {'yes' if os.path.exists(INDEX_FILENAME) else 'no'}")

    return "\n".join(info)


@mcp.resource("project://structure")
def get_project_structure() -> str:
    def build_tree(path, prefix="", max_depth=4, current_depth=0):
        if current_depth >= max_depth:
            return ""
        try:
            items = sorted([item for item in os.listdir(path) if not item.startswith('.')])
        except PermissionError:
            return f"{prefix}❌ Permission denied\n"
        tree = ""
        for i, item in enumerate(items):
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
                content = safe_read_text(file_path, max_chars=5000)
                found_deps.append(f"📋 {description} ({dep_file}):\n{'-'*50}\n{content}\n")
            except Exception as e:
                found_deps.append(f"❌ Error reading {dep_file}: {str(e)}\n")

    return "\n".join(found_deps) if found_deps else "❌ No dependency files found"


# =============================================================================
# HELPERS FOR LLM / USAGE
# =============================================================================

@mcp.tool()
def estimate_tokens(file_paths: List[str]) -> str:
    try:
        estim = []
        total_chars = 0
        for rel in file_paths:
            abs_p = validate_path(rel)
            if not os.path.exists(abs_p):
                estim.append(f"❌ Not found: {rel}")
                continue
            if is_binary_file(abs_p):
                estim.append(f"⚠️ Binary: {rel}")
                continue
            size = os.path.getsize(abs_p)
            total_chars += size
            tokens = max(1, int(size / 4))
            estim.append(f"{rel}: {size} bytes ≈ {tokens} tokens")
        total_tokens = int(total_chars / 4)
        estim.append(f"\nTotal chars: {total_chars} → ≈ {total_tokens} tokens")
        return "\n".join(estim)
    except Exception as e:
        return f"❌ Error estimating tokens: {str(e)}"


@mcp.tool()
def list_large_files(min_size_mb: int = 5, limit: int = 20) -> str:
    try:
        hits = []
        for root, _, files in os.walk(WORKING_DIR):
            if any(skip in root for skip in ['.git', 'node_modules', 'dist', 'build']):
                continue
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    size = os.path.getsize(fpath)
                except Exception:
                    continue
                if size >= min_size_mb * 1024 * 1024:
                    rel = os.path.relpath(fpath, WORKING_DIR)
                    hits.append((size, rel))
        hits.sort(reverse=True)
        out = [f"📁 Large files (>={min_size_mb}MB):"]
        for size, rel in hits[:limit]:
            out.append(f"• {rel} ({size/(1024*1024):.2f} MB)")
        if len(hits) == 0:
            return f"✅ No files >= {min_size_mb} MB found"
        return "\n".join(out)
    except Exception as e:
        return f"❌ Error listing large files: {str(e)}"


# =============================================================================
# SERVER STARTUP
# =============================================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")
