"""
Tests for ComposerResolver — PSR-4 + PSR-0 namespace resolution.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.composer_resolver import ComposerResolver


def _write_composer(root: Path, data: dict) -> None:
    (root / "composer.json").write_text(json.dumps(data), encoding="utf-8")


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<?php\n", encoding="utf-8")


# ── PSR-4 ───────────────────────────────────────────────────────────────────


def test_psr4_simple_namespace(tmp_path: Path):
    _write_composer(tmp_path, {"autoload": {"psr-4": {"App\\": "app/"}}})
    _touch(tmp_path / "app/Services/UserService.php")

    resolver = ComposerResolver(tmp_path)
    result = resolver.resolve("App\\Services\\UserService")

    assert result is not None
    assert result == (tmp_path / "app/Services/UserService.php")


def test_psr4_nested_namespace(tmp_path: Path):
    _write_composer(tmp_path, {"autoload": {"psr-4": {"App\\": "app/"}}})
    _touch(tmp_path / "app/Http/Controllers/UserController.php")

    resolver = ComposerResolver(tmp_path)
    result = resolver.resolve("App\\Http\\Controllers\\UserController")

    assert result == (tmp_path / "app/Http/Controllers/UserController.php")


def test_psr4_trait_import(tmp_path: Path):
    _write_composer(tmp_path, {"autoload": {"psr-4": {"App\\": "app/"}}})
    _touch(tmp_path / "app/Traits/HasUuid.php")

    resolver = ComposerResolver(tmp_path)
    assert resolver.resolve("App\\Traits\\HasUuid") == (tmp_path / "app/Traits/HasUuid.php")


def test_psr4_leading_backslash_normalized(tmp_path: Path):
    """`\\App\\Services\\Foo` should resolve the same as `App\\Services\\Foo`."""
    _write_composer(tmp_path, {"autoload": {"psr-4": {"App\\": "app/"}}})
    _touch(tmp_path / "app/Services/Foo.php")

    resolver = ComposerResolver(tmp_path)
    assert resolver.resolve("\\App\\Services\\Foo") == (tmp_path / "app/Services/Foo.php")


def test_psr4_longest_prefix_wins(tmp_path: Path):
    """When both App\\ and App\\Admin\\ match, the more specific prefix is used."""
    _write_composer(
        tmp_path,
        {"autoload": {"psr-4": {"App\\": "app/", "App\\Admin\\": "admin/"}}},
    )
    # Only create the file under the specific prefix's base dir
    _touch(tmp_path / "admin/User.php")

    resolver = ComposerResolver(tmp_path)
    result = resolver.resolve("App\\Admin\\User")

    assert result == (tmp_path / "admin/User.php")


def test_psr4_path_as_list(tmp_path: Path):
    """PSR-4 base dirs can be a list[str]. Resolver should try each."""
    _write_composer(
        tmp_path, {"autoload": {"psr-4": {"App\\": ["src/", "app/"]}}}
    )
    _touch(tmp_path / "app/Foo.php")

    resolver = ComposerResolver(tmp_path)
    assert resolver.resolve("App\\Foo") == (tmp_path / "app/Foo.php")


def test_psr4_namespace_without_matching_prefix(tmp_path: Path):
    _write_composer(tmp_path, {"autoload": {"psr-4": {"App\\": "app/"}}})
    resolver = ComposerResolver(tmp_path)
    assert resolver.resolve("Symfony\\Component\\Foo") is None


def test_psr4_file_missing_on_disk(tmp_path: Path):
    """Autoload map matches but the file doesn't exist → None."""
    _write_composer(tmp_path, {"autoload": {"psr-4": {"App\\": "app/"}}})
    # NOTE: no file created
    resolver = ComposerResolver(tmp_path)
    assert resolver.resolve("App\\Services\\Missing") is None


# ── PSR-0 fallback ──────────────────────────────────────────────────────────


def test_psr0_fallback(tmp_path: Path):
    """If no PSR-4 matches, fall through to PSR-0."""
    _write_composer(
        tmp_path, {"autoload": {"psr-0": {"Legacy\\": "legacy/"}}}
    )
    _touch(tmp_path / "legacy/Legacy/Something/Foo.php")

    resolver = ComposerResolver(tmp_path)
    assert resolver.resolve("Legacy\\Something\\Foo") == (
        tmp_path / "legacy/Legacy/Something/Foo.php"
    )


# ── Missing / malformed composer.json ──────────────────────────────────────


def test_missing_composer_json(tmp_path: Path):
    resolver = ComposerResolver(tmp_path)
    assert resolver.load() is False
    assert resolver.resolve("App\\Services\\Foo") is None


def test_malformed_composer_json(tmp_path: Path):
    (tmp_path / "composer.json").write_text("{ not valid json", encoding="utf-8")

    resolver = ComposerResolver(tmp_path)
    assert resolver.load() is False
    assert resolver.resolve("App\\Services\\Foo") is None


def test_composer_json_not_an_object(tmp_path: Path):
    """composer.json containing a JSON array/primitive is gracefully ignored."""
    (tmp_path / "composer.json").write_text("[]", encoding="utf-8")

    resolver = ComposerResolver(tmp_path)
    assert resolver.load() is False
    assert resolver.resolve("App\\Foo") is None


# ── autoload-dev merge ──────────────────────────────────────────────────────


def test_autoload_dev_merge(tmp_path: Path):
    """Dev autoload entries are merged in so test classes can resolve too."""
    _write_composer(
        tmp_path,
        {
            "autoload": {"psr-4": {"App\\": "app/"}},
            "autoload-dev": {"psr-4": {"Tests\\": "tests/"}},
        },
    )
    _touch(tmp_path / "tests/Unit/SomeTest.php")

    resolver = ComposerResolver(tmp_path)
    assert resolver.resolve("Tests\\Unit\\SomeTest") == (
        tmp_path / "tests/Unit/SomeTest.php"
    )


# ── Edge: alias handling is upstream (the regex strips `as X`) ─────────────


def test_function_import_namespace_resolves_if_file_exists(tmp_path: Path):
    """
    `use function App\\helpers\\str_slug;` → resolver gets "App\\helpers\\str_slug".
    If a file exists at that path it resolves; otherwise None. Either way no crash.
    """
    _write_composer(tmp_path, {"autoload": {"psr-4": {"App\\": "app/"}}})
    _touch(tmp_path / "app/helpers/str_slug.php")

    resolver = ComposerResolver(tmp_path)
    # Whether or not this is semantically "correct" PHP (function imports
    # don't follow PSR-4), we at least ensure we don't crash and return a
    # file path when one exists.
    assert resolver.resolve("App\\helpers\\str_slug") == (
        tmp_path / "app/helpers/str_slug.php"
    )


def test_function_import_missing_returns_none(tmp_path: Path):
    _write_composer(tmp_path, {"autoload": {"psr-4": {"App\\": "app/"}}})
    resolver = ComposerResolver(tmp_path)
    assert resolver.resolve("App\\helpers\\no_such_fn") is None
