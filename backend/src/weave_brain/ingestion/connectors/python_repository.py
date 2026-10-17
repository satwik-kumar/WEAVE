"""Python repository connector using AST parsing for repository, file, and import graphs."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from weave_brain.domain.models import RelationshipEdge, SourceArtifact


def _is_test_file(rel_path: Path) -> bool:
    """Return True if the file is considered a test file."""
    name = rel_path.name.lower()
    if name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py":
        return True
    parts = [p.lower() for p in rel_path.parts]
    return "tests" in parts or "test" in parts


def _build_module_map(repo_root: Path, py_files: list[Path]) -> dict[str, str]:
    """Build a mapping from importable module names to forward-slash relative file paths."""
    module_map: dict[str, str] = {}

    for file_path in py_files:
        rel_path = file_path.relative_to(repo_root)
        rel_str = rel_path.as_posix()

        # Dotted module path from repo_root
        parts = list(rel_path.parts)
        parts[-1] = parts[-1].removesuffix(".py")

        if parts[-1] == "__init__":
            parts = parts[:-1]

        if parts:
            dotted = ".".join(parts)
            module_map[dotted] = rel_str

            # Strip leading 'src' if present (e.g. src.auth.tokens -> auth.tokens)
            if parts[0] == "src" and len(parts) > 1:
                module_map[".".join(parts[1:])] = rel_str

        # Also map filename stem directly
        stem = file_path.stem
        if stem != "__init__":
            module_map.setdefault(stem, rel_str)

    return module_map


def _resolve_relative_import(
    current_rel_path: Path, level: int, module: str | None, repo_root: Path
) -> str | None:
    """Resolve a relative import (level > 0) to a forward-slash relative file path."""
    current_dir = current_rel_path.parent
    for _ in range(level - 1):
        current_dir = current_dir.parent

    target_parts = list(current_dir.parts)
    if module:
        target_parts.extend(module.split("."))

    # Check target as a .py file
    candidate_file = repo_root.joinpath(*target_parts).with_suffix(".py")
    if candidate_file.is_file():
        return candidate_file.relative_to(repo_root).as_posix()

    # Check target as a package __init__.py
    candidate_pkg = repo_root.joinpath(*target_parts, "__init__.py")
    if candidate_pkg.is_file():
        return candidate_pkg.relative_to(repo_root).as_posix()

    return None


def parse_python_file(
    file_path: Path,
    repo_slug: str,
    repo_root: Path,
    module_map: dict[str, str] | None = None,
) -> SourceArtifact:
    """Parse a single Python file into a File SourceArtifact.

    Extracts internal imports as ('IMPORTS', target_file_id) relationships.
    Strictly catches SyntaxError during ast.parse(), setting properties['parse_error'].
    """
    path = Path(file_path).resolve()
    root = Path(repo_root).resolve()

    rel_path = path.relative_to(root)
    rel_str = rel_path.as_posix()
    canonical_id = f"file:{repo_slug}:{rel_str}"

    raw_bytes = path.read_bytes()
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        source_code = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        source_code = raw_bytes.decode("latin-1", errors="replace")

    is_test = _is_test_file(rel_path)
    properties: dict[str, Any] = {
        "language": "Python",
        "is_test": is_test,
        "content_hash": content_hash,
    }

    tree: ast.AST | None = None
    try:
        tree = ast.parse(source_code, filename=str(path))
    except SyntaxError as e:
        properties["parse_error"] = str(e)

    relationships: list[RelationshipEdge] = []
    seen_targets: set[str] = set()

    if tree is not None and module_map is not None:
        for node in ast.walk(tree):
            resolved_rel_path: str | None = None

            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Look up exact module name or prefix
                    name = alias.name
                    if name in module_map:
                        resolved_rel_path = module_map[name]
                    elif "." in name:
                        top = name.split(".")[0]
                        if top in module_map:
                            resolved_rel_path = module_map[top]

            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    # Relative import
                    resolved_rel_path = _resolve_relative_import(
                        rel_path, node.level, node.module, root
                    )
                elif node.module:
                    # Absolute import within repo
                    if node.module in module_map:
                        resolved_rel_path = module_map[node.module]
                    else:
                        top = node.module.split(".")[0]
                        if top in module_map:
                            resolved_rel_path = module_map[top]

            if resolved_rel_path and resolved_rel_path != rel_str:
                target_file_id = f"file:{repo_slug}:{resolved_rel_path}"
                if target_file_id not in seen_targets:
                    seen_targets.add(target_file_id)
                    relationships.append(("IMPORTS", target_file_id))

    return SourceArtifact(
        source_id=f"{repo_slug}:{rel_str}",
        source_type="git",
        entity_type="file",
        canonical_id=canonical_id,
        title=rel_str,
        properties=properties,
        relationships=relationships,
        content_hash=content_hash,
    )


def parse_python_repository(
    repo_path: Path | str,
    repo_slug: str,
    repo_title: str | None = None,
    repo_url: str | None = None,
) -> list[SourceArtifact]:
    """Parse a local Python repository into a Repository artifact and File artifacts.

    Builds (:Repository)-[:CONTAINS]->(:File) and (:File)-[:IMPORTS]->(:File) edges.
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Repository directory not found: {root}")

    title = repo_title or repo_slug
    repo_canonical_id = f"repository:{repo_slug}"

    # Gather all Python files in deterministic sorted order
    all_py_files = sorted(
        p for p in root.rglob("*.py")
        if not any(part.startswith(".") or part in ("__pycache__", "venv", ".venv") for part in p.parts)
    )

    module_map = _build_module_map(root, all_py_files)
    file_artifacts: list[SourceArtifact] = []

    for file_path in all_py_files:
        file_artifact = parse_python_file(
            file_path=file_path,
            repo_slug=repo_slug,
            repo_root=root,
            module_map=module_map,
        )
        file_artifacts.append(file_artifact)

    # Repository artifact CONTAINS all files
    repo_relationships: list[RelationshipEdge] = [
        ("CONTAINS", f.canonical_id) for f in file_artifacts
    ]

    repo_properties: dict[str, Any] = {
        "language": "Python",
        "file_count": len(file_artifacts),
    }
    if repo_url:
        repo_properties["url"] = repo_url

    repo_artifact = SourceArtifact(
        source_id=f"repo-{repo_slug.replace('/', '-')}",
        source_type="git",
        entity_type="repository",
        canonical_id=repo_canonical_id,
        title=title,
        properties=repo_properties,
        relationships=repo_relationships,
        source_url=repo_url,
    )

    return [repo_artifact, *file_artifacts]
