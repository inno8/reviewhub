"""
Diff Extractor - Extract and parse git diffs.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import asyncio

from app.core.config import settings


class DiffExtractor:
    """
    Extract diffs from git repositories.
    
    Handles:
    - Cloning/caching repos
    - Extracting commit diffs
    - Parsing diff output
    """
    
    def __init__(self):
        self.cache_dir = Path(settings.GIT_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_repo_path(self, repo_url: str) -> Path:
        """Get local cache path for a repository."""
        # Convert URL to safe directory name
        # https://github.com/owner/repo.git -> owner_repo
        parts = repo_url.rstrip("/").rstrip(".git").split("/")
        repo_name = f"{parts[-2]}_{parts[-1]}"
        return self.cache_dir / repo_name
    
    async def _clone_or_fetch(self, repo_url: str) -> Path:
        """Clone repository or fetch updates if already cached."""
        repo_path = self._get_repo_path(repo_url)
        
        if repo_path.exists():
            # Fetch latest
            await asyncio.to_thread(
                subprocess.run,
                ["git", "fetch", "--all"],
                cwd=repo_path,
                capture_output=True,
                check=True
            )
        else:
            # Clone
            await asyncio.to_thread(
                subprocess.run,
                ["git", "clone", "--bare", repo_url, str(repo_path)],
                capture_output=True,
                check=True
            )
        
        return repo_path
    
    async def extract_commit_diff(
        self,
        repo_url: str,
        commit_sha: str
    ) -> Optional[dict]:
        """
        Extract diff for a specific commit.
        
        Returns:
            {
                "commit_sha": "abc123",
                "files": [
                    {
                        "path": "src/file.py",
                        "language": "python",
                        "diff": "...",
                        "additions": 10,
                        "deletions": 5
                    }
                ],
                "lines_added": 10,
                "lines_removed": 5
            }
        """
        try:
            repo_path = await self._clone_or_fetch(repo_url)
            
            # Get diff for commit
            result = await asyncio.to_thread(
                subprocess.run,
                ["git", "show", "--format=", "--patch", "--no-color", commit_sha],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Git error: {result.stderr}")
                return None
            
            # Parse diff output
            return self._parse_diff(commit_sha, result.stdout)
            
        except Exception as e:
            print(f"Error extracting diff: {e}")
            return None
    
    def _parse_diff(self, commit_sha: str, diff_output: str) -> dict:
        """Parse git diff output into structured data."""
        files = []
        current_file = None
        current_diff_lines = []
        total_added = 0
        total_removed = 0
        
        for line in diff_output.split("\n"):
            # New file
            if line.startswith("diff --git"):
                # Save previous file
                if current_file:
                    files.append({
                        "path": current_file,
                        "language": self._detect_language(current_file),
                        "diff": "\n".join(current_diff_lines),
                        "additions": sum(1 for l in current_diff_lines if l.startswith("+")),
                        "deletions": sum(1 for l in current_diff_lines if l.startswith("-"))
                    })
                
                # Extract new file path
                parts = line.split(" b/")
                if len(parts) > 1:
                    current_file = parts[1]
                else:
                    current_file = line.split()[-1]
                current_diff_lines = [line]
            
            elif current_file:
                current_diff_lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    total_added += 1
                elif line.startswith("-") and not line.startswith("---"):
                    total_removed += 1
        
        # Don't forget the last file
        if current_file:
            files.append({
                "path": current_file,
                "language": self._detect_language(current_file),
                "diff": "\n".join(current_diff_lines),
                "additions": sum(1 for l in current_diff_lines if l.startswith("+")),
                "deletions": sum(1 for l in current_diff_lines if l.startswith("-"))
            })
        
        return {
            "commit_sha": commit_sha,
            "files": files,
            "lines_added": total_added,
            "lines_removed": total_removed
        }
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".vue": "vue",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".less": "less",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".xml": "xml",
            ".md": "markdown",
            ".sql": "sql",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "zsh",
            ".ps1": "powershell",
        }
        
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext, "unknown")
