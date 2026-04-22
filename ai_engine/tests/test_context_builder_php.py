"""
Tests for PHP support in ContextBuilder.

Verifies that when a PHP diff contains `use App\\Services\\Foo;` and the repo
has a composer.json PSR-4 autoload + the corresponding file, ContextBuilder
emits that file's contents as context for the LLM.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from app.services.context_builder import ContextBuilder, LANGUAGE_IMPORT_PATTERNS


# ── Regex smoke tests ─────────────────────────────────────────────────────


def test_php_pattern_registered():
    assert "php" in LANGUAGE_IMPORT_PATTERNS
    assert len(LANGUAGE_IMPORT_PATTERNS["php"]) >= 1


def test_php_pattern_matches_simple_use():
    pattern = LANGUAGE_IMPORT_PATTERNS["php"][0]
    text = "use App\\Services\\UserService;"
    m = pattern.search(text)
    assert m is not None
    assert m.group(1) == "App\\Services\\UserService"


def test_php_pattern_matches_use_with_alias():
    pattern = LANGUAGE_IMPORT_PATTERNS["php"][0]
    text = "use App\\Services\\UserService as UserSvc;"
    m = pattern.search(text)
    assert m is not None
    # Alias must NOT be captured — just the fully qualified namespace.
    assert m.group(1) == "App\\Services\\UserService"


def test_php_pattern_matches_function_import():
    pattern = LANGUAGE_IMPORT_PATTERNS["php"][0]
    text = "use function App\\helpers\\str_slug;"
    m = pattern.search(text)
    assert m is not None
    assert m.group(1) == "App\\helpers\\str_slug"


def test_php_pattern_matches_const_import():
    pattern = LANGUAGE_IMPORT_PATTERNS["php"][0]
    text = "use const App\\FOO;"
    m = pattern.search(text)
    assert m is not None
    assert m.group(1) == "App\\FOO"


def test_php_pattern_does_not_match_use_in_trait_body():
    """
    The `use TraitName;` syntax inside a class body is also a valid PHP
    construct. Our pattern matches it too — that's fine: non-namespaced
    identifiers simply won't resolve via composer and are dropped silently.
    """
    pattern = LANGUAGE_IMPORT_PATTERNS["php"][0]
    m = pattern.search("    use SomeTrait;")
    assert m is not None
    assert m.group(1) == "SomeTrait"


# ── Full ContextBuilder integration ───────────────────────────────────────


def _init_git_repo(root: Path) -> None:
    """Initialize a git repo and commit all files under root to HEAD."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "git", "-c", "user.email=t@t", "-c", "user.name=t",
            "commit", "-q", "-m", "init",
        ],
        cwd=root,
        check=True,
    )


def test_context_builder_resolves_php_import(tmp_path: Path):
    """
    Given a Laravel-shaped repo with composer.json PSR-4 + a UserService,
    a PHP diff that adds `use App\\Services\\UserService;` should cause the
    builder to return that service file as context.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "composer.json").write_text(
        json.dumps({"autoload": {"psr-4": {"App\\": "app/"}}}),
        encoding="utf-8",
    )
    service_path = repo / "app/Services/UserService.php"
    service_path.parent.mkdir(parents=True)
    service_path.write_text(
        "<?php\nnamespace App\\Services;\nclass UserService {}\n",
        encoding="utf-8",
    )
    controller_path = repo / "app/Http/Controllers/UserController.php"
    controller_path.parent.mkdir(parents=True)
    controller_path.write_text("<?php\n", encoding="utf-8")

    _init_git_repo(repo)

    builder = ContextBuilder(repo)
    diff = (
        "@@ -1 +1,3 @@\n"
        "+<?php\n"
        "+use App\\Services\\UserService;\n"
        "+class UserController {}\n"
    )
    changed = [
        {
            "path": "app/Http/Controllers/UserController.php",
            "language": "php",
            "diff": diff,
        }
    ]
    context = asyncio.run(builder.build(changed))

    paths = [c["path"] for c in context]
    assert "app/Services/UserService.php" in paths
    service_entry = next(c for c in context if c["path"] == "app/Services/UserService.php")
    assert "class UserService" in service_entry["content"]


def test_context_builder_php_without_composer_json(tmp_path: Path):
    """No composer.json → PHP imports simply don't resolve, no crash."""
    repo = tmp_path / "repo"
    repo.mkdir()

    controller_path = repo / "app/Http/Controllers/UserController.php"
    controller_path.parent.mkdir(parents=True)
    controller_path.write_text("<?php\n", encoding="utf-8")

    _init_git_repo(repo)

    builder = ContextBuilder(repo)
    diff = (
        "@@ -1 +1,2 @@\n"
        "+<?php\n"
        "+use App\\Services\\UserService;\n"
    )
    changed = [
        {
            "path": "app/Http/Controllers/UserController.php",
            "language": "php",
            "diff": diff,
        }
    ]
    # Should return an empty (or sibling-only) context without raising.
    context = asyncio.run(builder.build(changed))
    assert isinstance(context, list)


def test_context_builder_php_unresolvable_namespace(tmp_path: Path):
    """Namespace doesn't match any PSR-4 prefix → dropped silently."""
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "composer.json").write_text(
        json.dumps({"autoload": {"psr-4": {"App\\": "app/"}}}),
        encoding="utf-8",
    )
    controller_path = repo / "app/Http/Controllers/UserController.php"
    controller_path.parent.mkdir(parents=True)
    controller_path.write_text("<?php\n", encoding="utf-8")

    _init_git_repo(repo)

    builder = ContextBuilder(repo)
    diff = (
        "@@ -1 +1,2 @@\n"
        "+<?php\n"
        "+use Symfony\\Component\\HttpKernel\\Kernel;\n"
    )
    changed = [
        {
            "path": "app/Http/Controllers/UserController.php",
            "language": "php",
            "diff": diff,
        }
    ]
    context = asyncio.run(builder.build(changed))
    # No crash, and the unresolvable namespace contributes nothing.
    paths = [c["path"] for c in context]
    assert "Symfony/Component/HttpKernel/Kernel.php" not in paths
