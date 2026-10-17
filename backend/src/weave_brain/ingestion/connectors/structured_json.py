"""Structured JSON connector for loading SourceArtifact records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from weave_brain.domain.models import SourceArtifact


def load_json_file(path: Path | str) -> list[SourceArtifact]:
    """Load and validate SourceArtifact records from a single JSON file.

    Raises FileNotFoundError if file does not exist,
    ValueError if JSON root is not a list,
    or ValidationError if any record fails schema validation.
    """
    file_path = Path(path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"JSON artifact file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        data: Any = json.load(f)

    if not isinstance(data, list):
        raise TypeError(
            f"Expected a top-level list of records in {file_path}, got {type(data).__name__}"
        )

    artifacts: list[SourceArtifact] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise TypeError(
                f"Item at index {idx} in {file_path} must be a dictionary, got {type(item).__name__}"
            )
        try:
            artifact = SourceArtifact.model_validate(item)
            artifacts.append(artifact)
        except ValidationError as e:
            raise ValidationError.from_exception_data(
                title=f"Error validating {file_path.name} item #{idx}",
                line_errors=e.errors(),
            ) from e

    return artifacts


def load_json_directory(data_dir: Path | str) -> list[SourceArtifact]:
    """Load and validate all JSON files in a directory in deterministic sorted order.

    Raises FileNotFoundError if directory does not exist or is not a directory.
    """
    dir_path = Path(data_dir).resolve()
    if not dir_path.is_dir():
        raise FileNotFoundError(f"JSON artifact directory not found: {dir_path}")

    json_files = sorted(dir_path.glob("*.json"))
    artifacts: list[SourceArtifact] = []

    for file_path in json_files:
        file_artifacts = load_json_file(file_path)
        artifacts.extend(file_artifacts)

    return artifacts
