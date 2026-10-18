"""Citation extraction and verification for WEAVE AI agent (Task D-R2).

Extracts cited canonical entity identifiers (type:slug) from generated answers,
verifies their presence against the retrieved evidence and GraphView, flags or removes
unverified claims, and generates actionable warning diagnostics.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from weave_brain.domain.models import ChatResponse, EvidenceItem, GraphView

# Canonical entity ID pattern: type:slug (e.g. service:authentication-api, decision:adr-001)
CITATION_PATTERN = re.compile(r"\b([a-zA-Z0-9_-]+:[a-zA-Z0-9_./-]+)\b")

# Protocols/schemas excluded from entity citation resolution
EXCLUDED_SCHEMAS = frozenset({"http", "https", "mailto", "ftp", "file", "ws", "wss"})


def extract_citations(text: str) -> list[str]:
    """Extract all candidate canonical entity identifiers cited in the text."""
    if not text:
        return []
    matches = CITATION_PATTERN.findall(text)
    citations: list[str] = []
    for m in matches:
        prefix = m.split(":", 1)[0].lower()
        if prefix not in EXCLUDED_SCHEMAS and m not in citations:
            citations.append(m)
    return citations


def get_valid_ids(
    evidence: Iterable[EvidenceItem] | None = None,
    graph: GraphView | None = None,
) -> set[str]:
    """Aggregate all valid, grounded entity IDs from evidence items and GraphView nodes."""
    valid: set[str] = set()
    if evidence:
        for ev in evidence:
            if ev.source_id:
                valid.add(ev.source_id)
            if getattr(ev, "relationship_path", None):
                valid.update(ev.relationship_path)
    if graph and graph.nodes:
        for node in graph.nodes:
            if node.id:
                valid.add(node.id)
    return valid


def verify_citations(
    answer: str,
    evidence: list[EvidenceItem] | None = None,
    graph: GraphView | None = None,
) -> tuple[str, list[str], list[str]]:
    """Verify all citations in the answer against evidence and graph.

    Returns:
        sanitized_answer: Text with unverified citations flagged as [UNVERIFIED: <id>].
        verified: List of verified citation IDs present in the graph evidence.
        warnings: List of warning strings detailing ungrounded citations.
    """
    cited_ids = extract_citations(answer)
    valid_ids = get_valid_ids(evidence, graph)

    verified: list[str] = []
    warnings: list[str] = []
    sanitized = answer

    for cid in cited_ids:
        if cid in valid_ids:
            verified.append(cid)
        else:
            warning_msg = (
                f"Unverified citation detected: '{cid}' is not grounded in graph evidence or GraphView."
            )
            warnings.append(warning_msg)
            # Flag unverified citation in the text
            sanitized = re.sub(
                rf"\b{re.escape(cid)}\b",
                f"[UNVERIFIED: {cid}]",
                sanitized,
            )

    return sanitized, verified, warnings


def verify_and_sanitize_response(response: ChatResponse) -> ChatResponse:
    """Verify all citations in a ChatResponse, flagging unverified claims and adding warnings."""
    if not response.answer:
        return response

    sanitized_answer, _, citation_warnings = verify_citations(
        answer=response.answer,
        evidence=response.evidence,
        graph=response.graph,
    )

    response.answer = sanitized_answer
    if citation_warnings:
        existing_warnings = set(response.warnings)
        for w in citation_warnings:
            if w not in existing_warnings:
                response.warnings.append(w)
                existing_warnings.add(w)

    return response
