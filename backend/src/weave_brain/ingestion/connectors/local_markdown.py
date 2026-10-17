"""Local Markdown connector for parsing documentation and architecture decision records."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from weave_brain.domain.models import EntityType, RelationshipEdge, SourceArtifact


def _extract_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extract YAML-like frontmatter between leading '---' fences if present.

    Returns (metadata_dict, remaining_markdown_body).
    """
    metadata: dict[str, Any] = {}
    remaining_body = content

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return metadata, remaining_body

    closing_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            closing_idx = i
            break

    if closing_idx == -1:
        return metadata, remaining_body

    frontmatter_lines = lines[1:closing_idx]
    remaining_body = "\n".join(lines[closing_idx + 1:]).strip()

    current_list_key: str | None = None
    for line in frontmatter_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- ") and current_list_key:
            item_str = stripped[2:].strip()
            # Support JSON-like array notation e.g. - ["OWNS", "service:auth"]
            if item_str.startswith("[") and item_str.endswith("]"):
                try:
                    item_val = json.loads(item_str)
                    metadata[current_list_key].append(item_val)
                    continue
                except json.JSONDecodeError:
                    pass
            metadata[current_list_key].append(item_str)
            continue

        if ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip()

            if not val:
                current_list_key = key
                metadata[key] = []
                continue

            current_list_key = None
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            elif val.lower() == "true":
                val = True  # type: ignore[assignment]
            elif val.lower() == "false":
                val = False  # type: ignore[assignment]

            metadata[key] = val

    return metadata, remaining_body


def _extract_title_and_excerpt(
    body: str, fallback_title: str
) -> tuple[str, str]:
    """Extract first # header as title and first prose paragraph as excerpt."""
    title = fallback_title
    lines = body.splitlines()
    prose_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            if title == fallback_title:
                # Use first header found
                header_text = re.sub(r"^#+\s*", "", stripped).strip()
                if header_text:
                    title = header_text
            continue

        # Non-header line
        prose_lines.append(stripped)

    excerpt_text = " ".join(prose_lines)
    excerpt = excerpt_text[:280].strip() if excerpt_text else None
    return title, excerpt


def parse_markdown_file(
    path: Path | str,
    default_entity_type: str = "document",
    default_service_id: str | None = None,
) -> SourceArtifact:
    """Parse a Markdown file into a document or decision SourceArtifact.

    Extracts title from frontmatter or first heading, computes SHA-256 hash,
    and extracts body excerpt. Supports explicit relationships in frontmatter
    or attaches default DOCUMENTS / DECIDES_FOR edge to default_service_id.
    """
    file_path = Path(path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Markdown file not found: {file_path}")

    raw_text = file_path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    frontmatter, body = _extract_frontmatter(raw_text)

    # Determine entity_type
    raw_type = str(frontmatter.get("entity_type") or default_entity_type).lower()
    entity_type: EntityType = "decision" if raw_type == "decision" else "document"

    # Determine title and excerpt
    stem_title = file_path.stem.replace("-", " ").replace("_", " ").title()
    title_from_body, excerpt = _extract_title_and_excerpt(body, stem_title)
    title = str(frontmatter.get("title") or title_from_body)

    # Determine canonical ID
    slug = file_path.stem.lower().replace("_", "-")
    canonical_id = str(
        frontmatter.get("canonical_id") or f"{entity_type}:{slug}"
    )

    # Properties
    properties: dict[str, Any] = {}
    for k, v in frontmatter.items():
        if k not in (
            "canonical_id",
            "title",
            "entity_type",
            "relationships",
            "source_id",
            "source_type",
            "source_url",
        ):
            properties[k] = v

    if excerpt:
        properties.setdefault("content_excerpt", excerpt)

    # Relationships
    relationships: list[RelationshipEdge] = []
    if "relationships" in frontmatter and isinstance(
        frontmatter["relationships"], list
    ):
        for edge in frontmatter["relationships"]:
            if isinstance(edge, (list, tuple)) and len(edge) in (2, 3):
                relationships.append(tuple(edge))  # type: ignore[arg-type]

    # Default fallback relationship if no explicit relationship provided
    if not relationships and default_service_id:
        rel_type = "DECIDES_FOR" if entity_type == "decision" else "DOCUMENTS"
        relationships.append((rel_type, default_service_id))

    source_id = str(frontmatter.get("source_id") or file_path.stem)
    source_type = str(
        frontmatter.get("source_type") or ("adr" if entity_type == "decision" else "markdown")
    )
    source_url = frontmatter.get("source_url")

    return SourceArtifact(
        source_id=source_id,
        source_type=source_type,
        entity_type=entity_type,
        canonical_id=canonical_id,
        title=title,
        properties=properties,
        relationships=relationships,
        source_url=source_url,
        content_hash=content_hash,
    )


def parse_markdown_directory(
    data_dir: Path | str,
    default_entity_type: str = "document",
    default_service_id: str | None = None,
    recursive: bool = True,
) -> list[SourceArtifact]:
    """Parse all Markdown files in a directory in deterministic order."""
    dir_path = Path(data_dir).resolve()
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Markdown directory not found: {dir_path}")

    pattern = "**/*.md" if recursive else "*.md"
    md_files = sorted(dir_path.glob(pattern))

    artifacts: list[SourceArtifact] = []
    for file_path in md_files:
        artifact = parse_markdown_file(
            file_path,
            default_entity_type=default_entity_type,
            default_service_id=default_service_id,
        )
        artifacts.append(artifact)

    return artifacts
