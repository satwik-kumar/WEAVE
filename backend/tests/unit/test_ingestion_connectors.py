"""Unit tests for ingestion connectors (structured JSON, local Markdown, Python AST repository)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from weave_brain.domain.models import SourceArtifact
from weave_brain.ingestion.connectors.local_markdown import (
    parse_markdown_directory,
    parse_markdown_file,
)
from weave_brain.ingestion.connectors.python_repository import (
    parse_python_file,
    parse_python_repository,
)
from weave_brain.ingestion.connectors.structured_json import (
    load_json_directory,
    load_json_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEMO_DIR = REPO_ROOT / "data" / "demo"


# ==============================================================================
# 1. Structured JSON Connector Tests
# ==============================================================================

def test_load_json_file_valid():
    """Verify loading a valid demo JSON file returns typed SourceArtifact objects."""
    services_path = DEMO_DIR / "services.json"
    artifacts = load_json_file(services_path)
    assert len(artifacts) == 4
    for a in artifacts:
        assert isinstance(a, SourceArtifact)
        assert a.entity_type == "service"


def test_load_json_directory_all_demo_data():
    """Verify loading data/demo/ loads all 19 official frozen demo entities."""
    artifacts = load_json_directory(DEMO_DIR)
    assert len(artifacts) == 19
    ids = {a.canonical_id for a in artifacts}
    assert "service:authentication-api" in ids
    assert "team:platform-engineering" in ids
    assert "decision:adr-001" in ids


def test_load_json_file_not_found():
    """Verify FileNotFoundError when JSON file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_json_file(DEMO_DIR / "non_existent.json")


def test_load_json_directory_not_found():
    """Verify FileNotFoundError when directory does not exist."""
    with pytest.raises(FileNotFoundError):
        load_json_directory(DEMO_DIR / "non_existent_dir")


def test_load_json_file_invalid_root_type(tmp_path: Path):
    """Verify TypeError when JSON file does not contain a list at the top level."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    with pytest.raises(TypeError, match="top-level list"):
        load_json_file(bad_file)


def test_load_json_file_validation_error(tmp_path: Path):
    """Verify ValidationError when an item is missing required fields."""
    bad_file = tmp_path / "invalid_item.json"
    bad_file.write_text(json.dumps([{"source_id": "test"}]), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_json_file(bad_file)


# ==============================================================================
# 2. Local Markdown Connector Tests
# ==============================================================================

def test_parse_markdown_file_with_frontmatter(tmp_path: Path):
    """Verify parsing a markdown file with YAML frontmatter."""
    md_file = tmp_path / "adr-042.md"
    md_content = """---
title: Token Caching Policy
entity_type: decision
status: accepted
rationale: Reduce auth round trips
relationships:
  - ["DECIDES_FOR", "service:authentication-api"]
---
# Token Caching Policy

We decide to cache JWT verification keys in Redis memory.
This reduces latency across microservices.
"""
    md_file.write_text(md_content, encoding="utf-8")

    artifact = parse_markdown_file(md_file)
    assert artifact.entity_type == "decision"
    assert artifact.canonical_id == "decision:adr-042"
    assert artifact.title == "Token Caching Policy"
    assert artifact.properties.get("status") == "accepted"
    assert artifact.properties.get("rationale") == "Reduce auth round trips"
    assert ("DECIDES_FOR", "service:authentication-api") in artifact.relationships
    assert artifact.content_hash is not None
    assert len(artifact.content_hash) == 64
    assert "JWT verification keys" in artifact.properties["content_excerpt"]


def test_parse_markdown_file_without_frontmatter(tmp_path: Path):
    """Verify parsing a plain markdown file with first header and default service fallback."""
    md_file = tmp_path / "auth_operations.md"
    md_content = """# Auth Operations Guide

This guide describes how to operate the authentication service.
Includes emergency rotation procedures and health checks.
"""
    md_file.write_text(md_content, encoding="utf-8")

    artifact = parse_markdown_file(
        md_file,
        default_entity_type="document",
        default_service_id="service:authentication-api",
    )
    assert artifact.entity_type == "document"
    assert artifact.canonical_id == "document:auth-operations"
    assert artifact.title == "Auth Operations Guide"
    assert ("DOCUMENTS", "service:authentication-api") in artifact.relationships
    assert "emergency rotation" in artifact.properties["content_excerpt"]


def test_parse_markdown_directory(tmp_path: Path):
    """Verify directory traversal of markdown files."""
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("# Doc One\nContent one", encoding="utf-8")
    doc2 = tmp_path / "doc2.md"
    doc2.write_text("# Doc Two\nContent two", encoding="utf-8")

    artifacts = parse_markdown_directory(tmp_path)
    assert len(artifacts) == 2
    titles = {a.title for a in artifacts}
    assert titles == {"Doc One", "Doc Two"}


def test_parse_markdown_file_not_found():
    """Verify FileNotFoundError when markdown file does not exist."""
    with pytest.raises(FileNotFoundError):
        parse_markdown_file(Path("non_existent_file.md"))


# ==============================================================================
# 3. Python Repository AST Parser Tests
# ==============================================================================

def test_python_parser_file_ast_and_imports(tmp_path: Path):
    """Verify AST parsing extracts internal module imports adhering to (:File)-[:IMPORTS]->(:File)."""
    src_dir = tmp_path / "src" / "pkg"
    src_dir.mkdir(parents=True)

    utils_file = src_dir / "utils.py"
    utils_file.write_text("def helper():\n    return 42\n", encoding="utf-8")

    main_file = src_dir / "main.py"
    main_code = """from pkg.utils import helper

def run():
    return helper()
"""
    main_file.write_text(main_code, encoding="utf-8")

    # Build module map and parse main_file
    module_map = {"pkg.utils": "src/pkg/utils.py", "pkg.main": "src/pkg/main.py"}
    artifact = parse_python_file(
        file_path=main_file,
        repo_slug="acme/test-app",
        repo_root=tmp_path,
        module_map=module_map,
    )

    assert artifact.entity_type == "file"
    assert artifact.canonical_id == "file:acme/test-app:src/pkg/main.py"
    assert artifact.title == "src/pkg/main.py"
    assert artifact.properties["language"] == "Python"
    assert artifact.properties["is_test"] is False
    assert "parse_error" not in artifact.properties

    # Direction check: main.py points to utils.py
    assert ("IMPORTS", "file:acme/test-app:src/pkg/utils.py") in artifact.relationships


def test_python_parser_file_syntax_error_handling(tmp_path: Path):
    """Verify ast.parse catches SyntaxError, sets properties['parse_error'], and does not crash."""
    broken_file = tmp_path / "broken.py"
    broken_file.write_text("def broken_func(\n    # Missing closing paren\n", encoding="utf-8")

    artifact = parse_python_file(
        file_path=broken_file,
        repo_slug="acme/broken-app",
        repo_root=tmp_path,
    )

    assert artifact.entity_type == "file"
    assert artifact.canonical_id == "file:acme/broken-app:broken.py"
    assert "parse_error" in artifact.properties
    assert artifact.properties["parse_error"] is not None
    assert artifact.relationships == []


def test_python_parser_repository_contains_and_test_detection(tmp_path: Path):
    """Verify parse_python_repository builds (:Repository)-[:CONTAINS]->(:File) and flags test files."""
    src_dir = tmp_path / "src"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir()
    tests_dir.mkdir()

    app_py = src_dir / "app.py"
    app_py.write_text("class App: pass\n", encoding="utf-8")

    test_py = tests_dir / "test_app.py"
    test_py.write_text("from src.app import App\ndef test_app(): pass\n", encoding="utf-8")

    artifacts = parse_python_repository(
        repo_path=tmp_path,
        repo_slug="acme/sample-repo",
        repo_title="Sample Repo",
        repo_url="https://github.com/acme/sample-repo",
    )

    # 1 Repository + 2 Files = 3 artifacts
    assert len(artifacts) == 3

    repo = artifacts[0]
    assert repo.entity_type == "repository"
    assert repo.canonical_id == "repository:acme/sample-repo"
    assert repo.properties["url"] == "https://github.com/acme/sample-repo"

    # Repository CONTAINS both files
    contains_targets = [e[1] for e in repo.relationships if e[0] == "CONTAINS"]
    assert "file:acme/sample-repo:src/app.py" in contains_targets
    assert "file:acme/sample-repo:tests/test_app.py" in contains_targets

    # Check is_test flags
    file_map = {a.canonical_id: a for a in artifacts[1:]}
    assert file_map["file:acme/sample-repo:src/app.py"].properties["is_test"] is False
    assert file_map["file:acme/sample-repo:tests/test_app.py"].properties["is_test"] is True


def test_python_parser_malformed_file_resilience(tmp_path: Path):
    """Verify parse_python_repository continues without crashing when malformed files exist, setting parse_error."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    valid_py = src_dir / "valid.py"
    valid_py.write_text("def ok():\n    return 1\n", encoding="utf-8")

    broken_py = src_dir / "broken.py"
    broken_py.write_text("def broken_syntax(:\n", encoding="utf-8")

    artifacts = parse_python_repository(
        repo_path=tmp_path,
        repo_slug="acme/resilience-repo",
    )

    # 1 Repo + 2 Files
    assert len(artifacts) == 3
    file_map = {a.canonical_id: a for a in artifacts if a.entity_type == "file"}

    valid_artifact = file_map["file:acme/resilience-repo:src/valid.py"]
    assert "parse_error" not in valid_artifact.properties
    assert valid_artifact.properties["is_test"] is False

    broken_artifact = file_map["file:acme/resilience-repo:src/broken.py"]
    assert "parse_error" in broken_artifact.properties
    assert broken_artifact.properties["parse_error"] is not None
    assert broken_artifact.properties["is_test"] is False


# Backward-compatibility aliases
test_parse_python_file_ast_and_imports = test_python_parser_file_ast_and_imports
test_parse_python_file_syntax_error_handling = test_python_parser_file_syntax_error_handling
test_parse_python_repository_contains_and_test_detection = (
    test_python_parser_repository_contains_and_test_detection
)
