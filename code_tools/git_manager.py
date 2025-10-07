#ruff:noqa
"""
Git Manager for Codebase Management
Handles git operations and provides structured output for LLM context
"""

import os
import subprocess

# import json
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class GitStatus:
    """Git repository status information"""

    current_branch: str
    is_clean: bool
    modified_files: List[str]
    untracked_files: List[str]
    staged_files: List[str]
    ahead_behind: Optional[Dict[str, int]] = None  # {"ahead": 2, "behind": 1}


@dataclass
class GitBranch:
    """Git branch information"""

    name: str
    is_current: bool
    last_commit: str
    last_commit_message: str
    is_remote: bool = False


@dataclass
class GitCommit:
    """Git commit information"""

    hash: str
    short_hash: str
    author: str
    date: str
    message: str
    files_changed: List[str]
    insertions: int = 0
    deletions: int = 0


@dataclass
class GitDiff:
    """Git diff information"""

    file_path: str
    status: str  # M, A, D, R, etc.
    insertions: int
    deletions: int
    diff_content: Optional[str] = None


@dataclass
class GitResult:
    """Result of a git operation"""

    success: bool
    output: str
    error: Optional[str] = None
    return_code: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


class GitManager:
    """
    Git manager for version control operations
    Provides structured git information for LLM context
    """

    def __init__(self, working_dir: str):
        self.working_dir = Path(working_dir).resolve()

        # Check if this is a git repository
        self.git_dir = self.working_dir / ".codebase"
            # ADD DEBUG LOGGING:
        print("🔍 GitManager Debug:")
        print(f"   working_dir param: {working_dir}")
        print(f"   self.working_dir: {self.working_dir}")
        print(f"   self.git_dir: {self.git_dir}")
        print(f"   git_dir exists: {self.git_dir.exists()}")
        print(f"   current working directory: {working_dir}")
        self.is_git_repo = self._is_git_repository()
        self.stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "commits_made": 0,
            "last_operation": None,
        }
    async def initialize_codebase_repo(self) -> GitResult:
        """Initialize a new .codebase repository"""
        try:
            if self.is_git_repo:
                return GitResult(success=True, output="Codebase repository already exists")
            
            # Create .codebase directory and initialize
            self.git_dir.mkdir(exist_ok=True)
            result = await self._run_git_command(["init"])
            if not result.success:
                return GitResult(
                    success=False,
                    output="Failed to initialize git repository",
                    error=f"Git init failed: {result.error}"
                )
            config_commands = [
                ["config", "user.name", "AI Codebase Manager"],
                ["config", "user.email", "ai@codebase.local"],
                ["config", "init.defaultBranch", "master"]
            ]
            for cmd in config_commands:
                config_result = await self._run_git_command(cmd)
                if not config_result.success:
                    logger.warning(f"Config command failed: {' '.join(cmd)}")
            status_check = await self._run_git_command(["status", "--porcelain"])
            if status_check.success:
                # Add initial files for tracking
                add_result = await self._run_git_command(["add", "."])
                if add_result.success:
                    commit_result = await self._run_git_command([
                        "commit", "-m", "Initial commit - AI codebase tracking initialized"
                    ])
                    if not commit_result.success:
                        logger.warning("Initial commit failed, but repository is initialized")
            
            self.is_git_repo = True
            return GitResult(
                success=True,
                output="Codebase repository initialized successfully"
            )
            
        except Exception as e:
            return GitResult(
                success=False,
                output="Failed to initialize codebase repository",
                error=f"Initialization error: {str(e)}"
            )
    def _is_git_repository(self) -> bool:
        """Check if current directory is a git repository"""
        try:
            return self.git_dir.exists() and (self.git_dir/"HEAD").exists()
        except Exception:
            return False

    async def _run_git_command(self, args: List[str], timeout: int = 30) -> GitResult:
        """Run a git command and return structured result"""
        try:
            self.stats["total_operations"] += 1
            self.stats["last_operation"] = datetime.now().isoformat()

            logger.debug(f"Running git command: git {' '.join(args)}")
            print("🔍 Git Command Debug:")
            print(f"   Command: git --git-dir={self.git_dir} --work-tree={self.working_dir} {' '.join(args)}")
            print(f"   CWD: {self.working_dir}")
            result = subprocess.run(
                ["git", "--git-dir", str(self.git_dir), "--work-tree", str(self.working_dir)] + args,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            print(f"   Return code: {result.returncode}")
            print(f"   Stdout: {result.stdout}")
            print(f"   Stderr: {result.stderr}")
            if result.returncode == 0:
                self.stats["successful_operations"] += 1
                return GitResult(
                    success=True,
                    output=result.stdout.strip() if result.stdout else "",
                    return_code=result.returncode,
                )
            else:
                self.stats["failed_operations"] += 1
                return GitResult(
                    success=False,
                    output=result.stdout.strip() if result.stdout else "",
                    error=result.stderr.strip() if result.stderr else "",
                    return_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            self.stats["failed_operations"] += 1
            return GitResult(
                success=False,
                output="",
                error=f"Git command timed out after {timeout} seconds",
            )
        except Exception as e:
            self.stats["failed_operations"] += 1
            return GitResult(
                success=False, output="", error=f"Git command failed: {str(e)}"
            )

    async def get_status(self) -> GitResult:
        """Get comprehensive git status"""
        if not self.is_git_repo:
            init_result = await self.initialize_codebase_repo()
            if not init_result.success:
               return GitResult(
                success=False, 
                output="error", 
                error="Failed to initialize codebase repository"
            )

        try:
            # Get current branch
            branch_result = await self._run_git_command(["branch", "--show-current"])
            if not branch_result.success:
                return branch_result

            current_branch = branch_result.output or "HEAD"

            # Get status --porcelain for clean parsing
            status_result = await self._run_git_command(["status", "--porcelain"])
            if not status_result.success:
                return status_result

            # Parse status output
            modified_files = []
            untracked_files = []
            staged_files = []
            if not status_result.output:
                return GitResult(
                    success=True, output="no status found", return_code=0                )
            for line in status_result.output.split("\n"):
                if not line.strip():
                    continue

                status_code = line[:2]
                file_path = line[3:]

                if status_code[0] in ["M", "A", "D", "R", "C"]:
                    staged_files.append(file_path)
                if status_code[1] in ["M", "D"]:
                    modified_files.append(file_path)
                if status_code == "??":
                    untracked_files.append(file_path)

            # Get ahead/behind info
            ahead_behind = None
            try:
                ahead_behind_result = await self._run_git_command(
                    [
                        "rev-list",
                        "--left-right",
                        "--count",
                        f"{current_branch}...origin/{current_branch}",
                    ]
                )
                if ahead_behind_result.success and ahead_behind_result.output:
                    parts = ahead_behind_result.output.split("\t")
                    if len(parts) == 2:
                        ahead_behind = {"ahead": int(parts[0]), "behind": int(parts[1])}
            except Exception:
                pass  # Remote tracking not available

            status = GitStatus(
                current_branch=current_branch,
                is_clean=len(modified_files) == 0
                and len(untracked_files) == 0
                and len(staged_files) == 0,
                modified_files=modified_files,
                untracked_files=untracked_files,
                staged_files=staged_files,
                ahead_behind=ahead_behind,
            )

            return GitResult(
                success=True,
                output=self._format_status_output(status),
                data={"status": asdict(status)},
            )

        except Exception as e:
            return GitResult(
                success=False,
                output="error",
                error=f"Failed to get git status: {str(e)}",
            )

    async def get_branches(self) -> GitResult:
        """Get all branches with information"""
        if not self.is_git_repo:
            return GitResult(
                success=False,
                output="error:git repo not found",
                error="Not a git repository",
            )

        try:
            # Get all branches with verbose info
            result = await self._run_git_command(["branch", "-av"])
            if not result.success:
                return result

            branches = []
            current_branch = None
            for line in result.output.split("\n"):
                if not line.strip():
                    continue

                line = line.strip()
                is_current = line.startswith("*")
                if is_current:
                    line = line[1:].strip()

                parts = line.split(None, 2)
                if len(parts) < 2:
                    continue

                name = parts[0]
                commit_hash = parts[1]
                message = parts[2] if len(parts) > 2 else ""

                # Skip remote tracking info lines
                if "->" in name:
                    continue

                is_remote = name.startswith("remotes/")
                if is_remote:
                    name = name[8:]  # Remove 'remotes/' prefix

                branch = GitBranch(
                    name=name,
                    is_current=is_current,
                    last_commit=commit_hash,
                    last_commit_message=message,
                    is_remote=is_remote,
                )

                branches.append(branch)
                if is_current:
                    current_branch = name

            return GitResult(
                success=True,
                output=self._format_branches_output(branches),
                data={
                    "branches": [asdict(b) for b in branches],
                    "current_branch": current_branch,
                },
            )

        except Exception as e:
            return GitResult(
                success=False,
                output=f"error:{e}",
                error=f"Failed to get branches: {str(e)}",
            )

    async def get_log(
        self, max_commits: int = 10, file_path: Optional[str] = None
    ) -> GitResult:
        """Get commit history"""
        if not self.is_git_repo:
            return GitResult(
                success=False, output="no git repo found", error="Not a git repository"
            )

        try:
            args = [
                "log",
                f"-{max_commits}",
                "--pretty=format:%H|%h|%an|%ad|%s",
                "--date=iso",
                "--stat",
            ]

            if file_path:
                args.extend(["--", file_path])

            result = await self._run_git_command(args)
            if not result.success:
                return result
            if not result.output:
                return GitResult(success=True, output="No commits found")

            commits = self._parse_log_output(result.output)

            return GitResult(
                success=True,
                output=self._format_log_output(commits),
                data={"commits": [asdict(c) for c in commits]},
            )

        except Exception as e:
            return GitResult(
                success=False,
                output=f"error:{e}",
                error=f"Failed to get git log: {str(e)}",
            )

    async def get_diff(
        self, file_path: Optional[str] = None, cached: bool = False
    ) -> GitResult:
        """Get diff information"""
        if not self.is_git_repo:
            return GitResult(
                success=False, output="no git repo found", error="Not a git repository"
            )

        try:
            args = ["diff", "--stat"]
            if cached:
                args.append("--cached")
            if file_path:
                args.extend(["--", file_path])

            result = await self._run_git_command(args)
            if not result.success:
                return result

            # Also get detailed diff if specific file requested
            detailed_diff = None
            if file_path:
                diff_args = ["diff"]
                if cached:
                    diff_args.append("--cached")
                diff_args.extend(["--", file_path])

                diff_result = await self._run_git_command(diff_args)
                if diff_result.success:
                    detailed_diff = diff_result.output

            return GitResult(
                success=True,
                output=result.output,
                data={
                    "stat_diff": result.output,
                    "detailed_diff": detailed_diff,
                    "file_path": file_path,
                },
            )

        except Exception as e:
            return GitResult(
                success=False,
                output="error has occured",
                error=f"Failed to get git diff: {str(e)}",
            )

    async def add_files(self, files: Union[str, List[str]]) -> GitResult:
        """Add files to git staging area"""
        if not self.is_git_repo:
            return GitResult(
                success=False, output="no git repo found", error="Not a git repository"
            )

        try:
            if isinstance(files, str):
                files = [files]

            args = ["add"] + files
            result = await self._run_git_command(args)

            return result

        except Exception as e:
            return GitResult(
                success=False,
                output="error has occured",
                error=f"Failed to add files: {str(e)}",
            )

    async def commit(
        self, message: str, files: Optional[List[str]] = None
    ) -> GitResult:
        """Commit changes"""
        if not self.is_git_repo:
            return GitResult(
                success=False, output="no git repo found", error="Not a git repository"
            )

        try:
            # Add files if specified
            if files:
                add_result = await self.add_files(files)
                if not add_result.success:
                    return add_result

            # Commit
            args = ["commit", "-m", message]
            result = await self._run_git_command(args)

            if result.success:
                self.stats["commits_made"] += 1

                # Get commit hash
                hash_result = await self._run_git_command(["rev-parse", "HEAD"])
                if hash_result.success and hash_result.output:
                    result.data = {"commit_hash": hash_result.output[:7]}

            return result

        except Exception as e:
            return GitResult(
                success=False,
                output="error has occured",
                error=f"Failed to commit: {str(e)}",
            )

    async def get_file_blame(self, file_path: str) -> GitResult:
        """Get line-by-line file history (blame)"""
        if not self.is_git_repo:
            return GitResult(
                success=False, output="no git repo found", error="Not a git repository"
            )

        try:
            args = ["blame", "--line-porcelain", file_path]
            result = await self._run_git_command(args)

            if result.success and result.output:
                # Parse blame output for summary
                lines = result.output.split("\n")
                authors = {}
                for line in lines:
                    if line.startswith("author "):
                        author = line[7:]
                        authors[author] = authors.get(author, 0) + 1

                result.data = {"authors": authors, "file_path": file_path}

            return result

        except Exception as e:
            return GitResult(
                success=False,
                output="error has occured",
                error=f"Failed to get blame for {file_path}: {str(e)}",
            )

    def _parse_log_output(self, output: str) -> List[GitCommit]:
        """Parse git log output into structured commits"""
        commits = []
        current_commit = None

        for line in output.split("\n"):
            if "|" in line and len(line.split("|")) == 5:
                # This is a commit header line
                if current_commit:
                    commits.append(current_commit)

                parts = line.split("|")
                current_commit = GitCommit(
                    hash=parts[0],
                    short_hash=parts[1],
                    author=parts[2],
                    date=parts[3],
                    message=parts[4],
                    files_changed=[],
                    insertions=0,
                    deletions=0,
                )
            elif current_commit and line.strip():
                # This is a file change line
                if "file" in line and ("insertion" in line or "deletion" in line):
                    # Parse insertions/deletions
                    parts = line.split(",")
                    for part in parts:
                        if "insertion" in part:
                            try:
                                current_commit.insertions = int(part.strip().split()[0])
                            except:
                                pass
                        if "deletion" in part:
                            try:
                                current_commit.deletions = int(part.strip().split()[0])
                            except:
                                pass
                else:
                    # File name
                    file_part = line.strip().split("|")[0].strip()
                    if file_part and file_part not in current_commit.files_changed:
                        current_commit.files_changed.append(file_part)

        if current_commit:
            commits.append(current_commit)

        return commits

    def _format_status_output(self, status: GitStatus) -> str:
        """Format git status for display"""
        output = []
        output.append("=== Git Status ===")
        output.append(f"Branch: {status.current_branch}")
        output.append(f"Status: {'Clean' if status.is_clean else 'Modified'}")

        if status.ahead_behind:
            ahead = status.ahead_behind.get("ahead", 0)
            behind = status.ahead_behind.get("behind", 0)
            if ahead or behind:
                output.append(f"Sync: {ahead} ahead, {behind} behind")

        if status.staged_files:
            output.append(f"\n📁 Staged files ({len(status.staged_files)}):")
            for f in status.staged_files:
                output.append(f"  + {f}")

        if status.modified_files:
            output.append(f"\n📝 Modified files ({len(status.modified_files)}):")
            for f in status.modified_files:
                output.append(f"  M {f}")

        if status.untracked_files:
            output.append(f"\n❓ Untracked files ({len(status.untracked_files)}):")
            for f in status.untracked_files[:5]:  # Limit to first 5
                output.append(f"  ? {f}")
            if len(status.untracked_files) > 5:
                output.append(f"  ... and {len(status.untracked_files) - 5} more")

        return "\n".join(output)

    def _format_branches_output(self, branches: List[GitBranch]) -> str:
        """Format branches for display"""
        output = []
        output.append("=== Git Branches ===")

        local_branches = [b for b in branches if not b.is_remote]
        remote_branches = [b for b in branches if b.is_remote]

        if local_branches:
            output.append("\n📍 Local branches:")
            for branch in local_branches:
                marker = "* " if branch.is_current else "  "
                output.append(
                    f"{marker}{branch.name:<20} {branch.last_commit[:7]} {branch.last_commit_message}"
                )

        if remote_branches:
            output.append("\n🌐 Remote branches:")
            for branch in remote_branches[:5]:  # Limit remote branches
                output.append(
                    f"  {branch.name:<20} {branch.last_commit[:7]} {branch.last_commit_message}"
                )
            if len(remote_branches) > 5:
                output.append(
                    f"  ... and {len(remote_branches) - 5} more remote branches"
                )

        return "\n".join(output)

    def _format_log_output(self, commits: List[GitCommit]) -> str:
        """Format commit log for display"""
        output = []
        output.append("=== Git Log ===")

        for i, commit in enumerate(commits, 1):
            output.append(f"\n{i}. {commit.short_hash} - {commit.message}")
            output.append(f"   👤 {commit.author} • 📅 {commit.date[:10]}")
            if commit.files_changed:
                files_str = ", ".join(commit.files_changed[:3])
                if len(commit.files_changed) > 3:
                    files_str += f" (+{len(commit.files_changed) - 3} more)"
                output.append(f"   📁 {files_str}")
            if commit.insertions or commit.deletions:
                output.append(f"   📊 +{commit.insertions} -{commit.deletions}")

        return "\n".join(output)

    def get_stats(self) -> Dict[str, Any]:
        """Get git manager statistics"""
        return {
            **self.stats,
            "is_git_repo": self.is_git_repo,
            "working_dir": str(self.working_dir),
        }
    
    
    async def checkout_branch(self, branch_name: str, create_new: bool = False) -> GitResult:
        """Checkout a branch, optionally creating it"""
        if not self.is_git_repo:
            return GitResult(success=False,output="no git repo found", error="Not a git repository")
        
        try:
            args = ['checkout']
            if create_new:
                args.append('-b')
            args.append(branch_name)
            
            result = await self._run_git_command(args)
            return result
            
        except Exception as e:
            return GitResult(
                success=False,
                output=f"Failed to checkout branch {branch_name}",
                error=f"Failed to checkout branch {branch_name}: {str(e)}"
            )
    
    async def create_branch(self, branch_name: str, switch_to: bool = True) -> GitResult:
        """Create a new branch and optionally switch to it"""
        if not self.is_git_repo:
            return GitResult(success=False, output="no git repo found", error="Not a git repository")
        
        try:
            if switch_to:
                result = await self.checkout_branch(branch_name, create_new=True)
            else:
                result = await self._run_git_command(['branch', branch_name])
            
            return result
            
        except Exception as e:
            return GitResult(
                success=False,
                output=f"Failed to create branch {branch_name}",
                error=f"Failed to create branch {branch_name}: {str(e)}"
            )
    
    async def delete_branch(self, branch_name: str, force: bool = False) -> GitResult:
        """Delete a branch"""
        if not self.is_git_repo:
            return GitResult(success=False,output="no git repo found", error="Not a git repository")
        
        try:
            args = ['branch', '-D' if force else '-d', branch_name]
            result = await self._run_git_command(args)
            return result
            
        except Exception as e:
            return GitResult(
                success=False,
                output=f"Failed to delete branch {branch_name}",
                error=f"Failed to delete branch {branch_name}: {str(e)}"
            )
    
    async def merge_branch(self, branch_name: str, message: Optional[str] = None) -> GitResult:
        """Merge a branch into current branch"""
        if not self.is_git_repo:
            return GitResult(success=False,output="no git repo found", error="Not a git repository")
        
        try:
            args = ['merge', branch_name]
            if message:
                args.extend(['-m', message])
            
            result = await self._run_git_command(args)
            return result
            
        except Exception as e:
            return GitResult(
                success=False,
                output=f"Failed to merge branch {branch_name}",
                error=f"Failed to merge branch {branch_name}: {str(e)}"
            )
    
    async def get_current_branch(self) -> GitResult:
        """Get current branch name"""
        if not self.is_git_repo:
            return GitResult(success=False,output="no git repo found", error="Not a git repository")
        
        try:
            result = await self._run_git_command(['branch', '--show-current'])
            if result.success:
                current_branch = result.output.strip()
                result.data = {'current_branch': current_branch}
            return result
            
        except Exception as e:
            return GitResult(
                success=False,
                output="Failed to get current branch",
                error=f"Failed to get current branch: {str(e)}"
            )
    
    async def list_session_branches(self) -> GitResult:
        """List all session branches (branches starting with 'ai-session-' or 'session-')"""
        try:
            branches_result = await self.get_branches()
            if not branches_result.success:
                return branches_result
            
            session_branches = []
            if branches_result.data and 'branches' in branches_result.data:
                for branch_info in branches_result.data['branches']:
                    branch_name = branch_info['name']
                    # if (branch_name.startswith('ai-session-') or 
                    #     branch_name.startswith('session-') or
                    #     branch_name.startswith('ai-') and 'session' in branch_name):
                    #     session_branches.append(branch_info)
                    session_branches.append(branch_info)
            
            output = "🌿 Session Branches:\n"
            if session_branches:
                for branch in session_branches:
                    marker = "* " if branch['is_current'] else "  "
                    output += f"{marker}{branch['name']} - {branch['last_commit_message'][:50]}\n"
            else:
                output += "No session branches found"
            
            return GitResult(
                success=True,
                output=output,
                data={'session_branches': session_branches}
            )
            
        except Exception as e:
            return GitResult(
                success=False,
                output="Failed to list session branches",
                error=f"Failed to list session branches: {str(e)}"
            )
    