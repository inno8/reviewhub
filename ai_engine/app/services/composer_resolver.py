"""
Resolves PHP namespaces to file paths using composer.json PSR-4 autoload.

Reference: https://getcomposer.org/doc/04-schema.md#autoload
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class ComposerResolver:
    """Parses composer.json autoload maps, resolves PHP namespaces to file paths."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self._psr4_map: dict[str, list[str]] = {}
        self._psr0_map: dict[str, list[str]] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load composer.json. Returns True if found and parsed, False otherwise."""
        composer_path = self.repo_root / "composer.json"
        if not composer_path.is_file():
            self._loaded = True
            return False

        try:
            data = json.loads(composer_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            self._loaded = True
            return False

        if not isinstance(data, dict):
            self._loaded = True
            return False

        # Merge "autoload" and "autoload-dev" maps.
        autoload = data.get("autoload") or {}
        autoload_dev = data.get("autoload-dev") or {}
        if not isinstance(autoload, dict):
            autoload = {}
        if not isinstance(autoload_dev, dict):
            autoload_dev = {}

        psr4_raw = {}
        psr4_raw.update(autoload.get("psr-4") or {})
        psr4_raw.update(autoload_dev.get("psr-4") or {})
        self._psr4_map = self._normalize_map(psr4_raw)

        psr0_raw = {}
        psr0_raw.update(autoload.get("psr-0") or {})
        psr0_raw.update(autoload_dev.get("psr-0") or {})
        self._psr0_map = self._normalize_map(psr0_raw)

        self._loaded = True
        return True

    @staticmethod
    def _normalize_map(raw: dict) -> dict[str, list[str]]:
        """Convert composer autoload values (can be str or list[str]) to list[str]."""
        normalized: dict[str, list[str]] = {}
        for prefix, paths in raw.items():
            if not isinstance(prefix, str):
                continue
            if isinstance(paths, str):
                normalized[prefix] = [paths]
            elif isinstance(paths, list):
                normalized[prefix] = [p for p in paths if isinstance(p, str)]
        return normalized

    def resolve(self, namespace: str) -> Optional[Path]:
        """
        Resolve a fully-qualified PHP namespace to a file path.

        Example:
          autoload map: {"App\\": "app/"}
          namespace:    "App\\Services\\UserService"
          returns:      repo_root / "app/Services/UserService.php"

        Returns None if no matching autoload prefix or file doesn't exist.
        """
        if not self._loaded:
            self.load()

        # Normalize leading backslash
        ns = namespace.lstrip("\\")
        if not ns:
            return None

        # PSR-4 first (modern standard, Laravel/Symfony use this)
        path = self._resolve_psr4(ns)
        if path and path.is_file():
            return path

        # PSR-0 fallback (legacy)
        path = self._resolve_psr0(ns)
        if path and path.is_file():
            return path

        return None

    def _resolve_psr4(self, ns: str) -> Optional[Path]:
        """PSR-4: prefix maps to base dir. Remaining parts map to subdirs."""
        # Match longest prefix first (more specific wins)
        prefixes = sorted(self._psr4_map.keys(), key=len, reverse=True)
        for prefix in prefixes:
            # PSR-4 prefixes end in \\ per the spec
            prefix_stripped = prefix.rstrip("\\")
            if prefix_stripped == "":
                # Empty-prefix PSR-4 ("" maps everything under base dir)
                relative = ns.replace("\\", "/") + ".php"
                for base_dir in self._psr4_map[prefix]:
                    path = self.repo_root / base_dir.rstrip("/") / relative
                    if path.is_file():
                        return path
                continue
            if ns.startswith(prefix_stripped + "\\") or ns == prefix_stripped:
                remainder = ns[len(prefix_stripped):].lstrip("\\")
                relative = remainder.replace("\\", "/") + ".php"
                for base_dir in self._psr4_map[prefix]:
                    path = self.repo_root / base_dir.rstrip("/") / relative
                    if path.is_file():
                        return path
        return None

    def _resolve_psr0(self, ns: str) -> Optional[Path]:
        """PSR-0: legacy. Prefix + remainder with underscores-as-dirs in class name."""
        prefixes = sorted(self._psr0_map.keys(), key=len, reverse=True)
        for prefix in prefixes:
            prefix_stripped = prefix.rstrip("\\")
            if prefix_stripped == "" or ns.startswith(prefix_stripped + "\\") or ns == prefix_stripped:
                # PSR-0: underscores in the class name become directory separators
                parts = ns.split("\\")
                last = parts[-1].replace("_", "/")
                relative = "/".join(parts[:-1] + [last]) + ".php"
                for base_dir in self._psr0_map[prefix]:
                    path = self.repo_root / base_dir.rstrip("/") / relative
                    if path.is_file():
                        return path
        return None
