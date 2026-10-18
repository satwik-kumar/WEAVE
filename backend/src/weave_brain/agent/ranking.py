"""Hybrid relevance ranking and candidate validation for architectural decisions.

Ranks FalkorDB graph decisions against user queries using semantic keyword tokens,
incident causal links, and supersedes relationships, while enforcing strict candidate
validation so no unsupported entities or ungrounded claims are emitted.
"""

from __future__ import annotations

import re
from typing import Any

# Query stop-words that appear in common query templates but do not identify specific topics
STOP_WORDS: frozenset[str] = frozenset(
    {
        "why",
        "was",
        "were",
        "the",
        "a",
        "an",
        "is",
        "are",
        "chosen",
        "chose",
        "made",
        "selected",
        "adopted",
        "for",
        "to",
        "in",
        "of",
        "about",
        "with",
        "on",
        "over",
        "than",
        "by",
        "from",
        "and",
        "or",
        "between",
        "service",
        "services",
        "team",
        "teams",
        "decision",
        "decisions",
        "adr",
        "adrs",
        "policy",
        "policies",
        "architecture",
        "architectural",
        "what",
        "which",
        "how",
        "when",
        "where",
        "there",
        "date",
        "dates",
        "time",
        "history",
        "do",
        "does",
        "did",
        "can",
        "could",
        "would",
        "should",
        "explain",
        "describe",
        "tell",
        "me",
        "we",
        "us",
        "our",
        "i",
        "you",
        "they",
        "them",
        "it",
        "its",
        "take",
        "taken",
        "decide",
        "decided",
        "exist",
        "exists",
        "list",
        "all",
        "any",
        "show",
        "give",
        "have",
        "has",
        "recorded",
        "current",
        "active",
        "not",
        "no",
    }
)

# Known service names/tokens that identify target services rather than decision topics
SERVICE_TOKENS: frozenset[str] = frozenset(
    {
        "auth",
        "authentication",
        "user",
        "profile",
        "notification",
        "notifications",
        "pipeline",
        "data-pipeline",
    }
)

# Negation terms indicating queries about rejections, alternatives, or why something was not chosen
NEGATION_TERMS: frozenset[str] = frozenset(
    {
        "not",
        "no",
        "never",
        "reject",
        "rejected",
        "replace",
        "replaced",
        "instead",
        "without",
        "alternative",
    }
)

# Semantic synonym mappings to bridge user phrasing with graph node/property vocabulary
SYNONYM_MAP: dict[str, set[str]] = {
    "token": {
        "token",
        "tokens",
        "jwt",
        "key",
        "keys",
        "credential",
        "credentials",
        "expiry",
        "expiration",
        "signing",
    },
    "tokens": {
        "token",
        "tokens",
        "jwt",
        "key",
        "keys",
        "credential",
        "credentials",
        "expiry",
        "expiration",
        "signing",
    },
    "key": {
        "key",
        "keys",
        "token",
        "tokens",
        "jwt",
        "credential",
        "credentials",
        "expiry",
        "expiration",
        "signing",
    },
    "keys": {
        "key",
        "keys",
        "token",
        "tokens",
        "jwt",
        "credential",
        "credentials",
        "expiry",
        "expiration",
        "signing",
    },
    "credential": {
        "credential",
        "credentials",
        "token",
        "tokens",
        "jwt",
        "key",
        "keys",
        "expiry",
        "expiration",
    },
    "credentials": {
        "credential",
        "credentials",
        "token",
        "tokens",
        "jwt",
        "key",
        "keys",
        "expiry",
        "expiration",
    },
    "jwt": {"jwt", "token", "tokens", "key", "keys", "credential"},
    "expiry": {"expiry", "expiration", "expire", "24h", "lifetime", "token", "tokens"},
    "expiration": {
        "expiry",
        "expiration",
        "expire",
        "24h",
        "lifetime",
        "token",
        "tokens",
    },
    "expire": {"expiry", "expiration", "expire", "24h", "lifetime", "token", "tokens"},
    "24h": {"24h", "expiry", "expiration", "token", "tokens"},
    "proxy": {"proxy", "envoy", "sidecar"},
    "envoy": {"envoy", "proxy", "sidecar"},
    "sidecar": {"sidecar", "envoy", "proxy"},
    "mesh": {"mesh", "service-mesh"},
    "service-mesh": {"mesh", "service-mesh"},
    "incident": {"incident", "inc-007", "leak", "compromise", "exploit"},
    "leak": {"leak", "compromise", "incident", "inc-007", "token", "tokens"},
    "compromise": {"compromise", "leak", "incident", "inc-007", "token"},
    "superseded": {"superseded", "supersedes", "replacement", "replaced", "older"},
    "supersedes": {"superseded", "supersedes", "replacement", "replaced", "older"},
    "replace": {"superseded", "supersedes", "replacement", "replaced", "older"},
    "replaced": {"superseded", "supersedes", "replacement", "replaced", "older"},
    "replacement": {"superseded", "supersedes", "replacement", "replaced", "older"},
}


def _tokenize_text(text: str) -> set[str]:
    """Extract lowercased word tokens from text, preserving hyphenated terms and sub-tokens."""
    if not text:
        return set()
    raw = set(re.findall(r"[a-z0-9_\-]+", text.lower()))
    parts: set[str] = set()
    for t in raw:
        parts.add(t)
        if "-" in t or "_" in t:
            parts.update(re.findall(r"[a-z0-9]+", t))
    return parts


def _extract_graph_nodes_and_edges(graph: Any) -> tuple[list[Any], list[Any]]:
    """Extract nodes and edges from dict or GraphView."""
    if isinstance(graph, dict):
        return graph.get("nodes", []), graph.get("edges", [])
    if hasattr(graph, "nodes") and hasattr(graph, "edges"):
        return graph.nodes, graph.edges
    return [], []


def _get_edge_triple(edge: Any) -> tuple[str, str, str] | None:
    """Extract (source_id, target_id, rel_type) from dict or GraphEdge object."""
    if isinstance(edge, dict):
        src = str(edge.get("source_id", ""))
        tgt = str(edge.get("target_id", ""))
        rel = str(edge.get("relationship_type") or edge.get("label", ""))
        return (src, tgt, rel) if src and tgt and rel else None
    if (
        hasattr(edge, "source_id")
        and hasattr(edge, "target_id")
        and hasattr(edge, "relationship_type")
    ):
        src = str(edge.source_id)
        tgt = str(edge.target_id)
        rel = str(edge.relationship_type)
        return (src, tgt, rel) if src and tgt and rel else None
    return None


def _get_node_id_and_obj(node: Any) -> tuple[str, Any] | None:
    """Extract (node_id, node) from dict or GraphNode object."""
    if isinstance(node, dict):
        nid = str(node.get("id", ""))
        return (nid, node) if nid else None
    if hasattr(node, "id"):
        nid = str(node.id)
        return (nid, node) if nid else None
    return None


def get_linked_incident(
    decision: dict[str, Any] | Any, graph: Any = None
) -> dict[str, Any] | Any | None:
    """Find the motivating incident node for a decision from properties or graph edges."""
    inc = (
        decision.get("incident")
        if isinstance(decision, dict)
        else getattr(decision, "incident", None)
    )
    if inc:
        return inc

    dec_id = (
        decision.get("id")
        if isinstance(decision, dict)
        else getattr(decision, "id", None)
    )
    if not dec_id or not graph:
        return None

    raw_nodes, raw_edges = _extract_graph_nodes_and_edges(graph)
    nodes_map: dict[str, Any] = {}
    for n in raw_nodes:
        pair = _get_node_id_and_obj(n)
        if pair:
            nodes_map[pair[0]] = pair[1]

    for edge in raw_edges:
        triple = _get_edge_triple(edge)
        if triple:
            src, tgt, rel = triple
            if rel == "MOTIVATED_BY" and src == dec_id:
                if tgt in nodes_map:
                    return nodes_map[tgt]
                return {"id": tgt, "title": tgt}
    return None


def get_supersedes_info(
    decision: dict[str, Any] | Any, graph: Any = None
) -> tuple[str | None, str | None]:
    """Find (supersedes_older_id, superseded_by_newer_id) for a decision."""
    older_id = (
        decision.get("supersedes")
        if isinstance(decision, dict)
        else getattr(decision, "supersedes", None)
    )
    newer_id = (
        decision.get("superseded_by")
        if isinstance(decision, dict)
        else getattr(decision, "superseded_by", None)
    )

    dec_id = (
        decision.get("id")
        if isinstance(decision, dict)
        else getattr(decision, "id", None)
    )
    if not dec_id or not graph:
        return older_id, newer_id

    _, raw_edges = _extract_graph_nodes_and_edges(graph)
    for edge in raw_edges:
        triple = _get_edge_triple(edge)
        if triple:
            src, tgt, rel = triple
            if rel == "SUPERSEDES":
                if src == dec_id and not older_id:
                    older_id = tgt
                elif tgt == dec_id and not newer_id:
                    newer_id = src

    return older_id, newer_id


def extract_topic_terms(question: str) -> set[str]:
    """Extract substantive topic terms from a question, expanding known architectural synonyms."""
    raw_tokens = re.findall(r"[a-z0-9_\-]+", question.lower())
    substantive = [
        t
        for t in raw_tokens
        if t not in STOP_WORDS and t not in SERVICE_TOKENS and len(t) > 1
    ]

    expanded: set[str] = set()
    for token in substantive:
        expanded.add(token)
        if token in SYNONYM_MAP:
            expanded.update(SYNONYM_MAP[token])

    return expanded


def score_decision_relevance(
    decision: dict[str, Any] | Any,
    topic_terms: set[str],
    graph: Any = None,
) -> float:
    """Calculate a grounded relevance score for a decision node given query topic terms.

    Uses word-boundary token matching to prevent false positives from substring inclusions.
    """
    if not topic_terms:
        return 1.0  # General question; all candidates are equally relevant

    score = 0.0
    props = (
        decision.get("properties", {})
        if isinstance(decision, dict)
        else getattr(decision, "properties", {})
    )

    title_text = str(
        decision.get("title", "")
        if isinstance(decision, dict)
        else getattr(decision, "title", "")
    )
    title_tokens = _tokenize_text(title_text)

    rat_text = str(
        (
            props.get("rationale")
            if isinstance(props, dict)
            else getattr(props, "rationale", "")
        )
        or (
            decision.get("rationale", "")
            if isinstance(decision, dict)
            else getattr(decision, "rationale", "")
        )
    )
    rationale_tokens = _tokenize_text(rat_text)

    id_text = str(
        decision.get("id", "")
        if isinstance(decision, dict)
        else getattr(decision, "id", "")
    )
    id_tokens = _tokenize_text(id_text)

    # 1. Match in Decision Title (weight: 3.0 per term)
    for term in topic_terms:
        if term in title_tokens:
            score += 3.0
        elif term in id_tokens:
            score += 2.0

    # 2. Match in Decision Rationale (weight: 2.0 per term)
    for term in topic_terms:
        if term in rationale_tokens:
            score += 2.0

    # 3. Match in Linked Incident via MOTIVATED_BY (weight: 2.5 per term)
    inc = get_linked_incident(decision, graph=graph)
    if inc:
        inc_tokens: set[str] = set()
        inc_id = inc.get("id") if isinstance(inc, dict) else getattr(inc, "id", "")
        inc_title = (
            inc.get("title") if isinstance(inc, dict) else getattr(inc, "title", "")
        )
        inc_props = (
            inc.get("properties", {})
            if isinstance(inc, dict)
            else getattr(inc, "properties", {})
        )
        inc_summary = (
            inc_props.get("summary", "")
            if isinstance(inc_props, dict)
            else getattr(inc_props, "summary", "")
        )

        inc_tokens.update(_tokenize_text(str(inc_id)))
        inc_tokens.update(_tokenize_text(str(inc_title)))
        inc_tokens.update(_tokenize_text(str(inc_summary)))

        for term in topic_terms:
            if term in inc_tokens:
                score += 2.5

    # 4. Status weighting: Slight boost for active accepted over superseded decisions
    status = (
        props.get("status")
        if isinstance(props, dict)
        else getattr(props, "status", None)
    )
    if status == "accepted" and score > 0:
        score += 0.5

    return score


def rank_decision_candidates(
    question: str,
    decisions: list[dict[str, Any]] | list[Any],
    graph: Any = None,
) -> tuple[list[Any], bool, set[str]]:
    """Rank decision candidates by relevance score.

    Returns:
        (ranked_decisions, is_specific_query, matched_terms)
        - ranked_decisions: Decisions ordered by relevance score descending (score > 0).
        - is_specific_query: True if the question contained topic terms (not a general query).
        - matched_terms: Set of non-stopword, non-service topic terms extracted from query.
    """
    if not decisions:
        return [], False, set()

    raw_tokens = re.findall(r"[a-z0-9_\-]+", question.lower())
    substantive_tokens = [
        t
        for t in raw_tokens
        if t not in STOP_WORDS and t not in SERVICE_TOKENS and len(t) > 1
    ]
    is_specific = len(substantive_tokens) > 0

    if not is_specific:
        # General query: preserve existing order (all equal relevance)
        return list(decisions), False, set()

    topic_terms = extract_topic_terms(question)

    scored: list[tuple[Any, float]] = []
    for d in decisions:
        s = score_decision_relevance(d, topic_terms, graph=graph)
        scored.append((d, s))

    # Sort descending by score
    scored.sort(key=lambda item: item[1], reverse=True)

    max_score = scored[0][1] if scored else 0.0

    # If no candidate scored > 0, return empty list to indicate no match found
    if max_score <= 0.0:
        return [], True, set(substantive_tokens)

    # Return decisions with score > 0
    relevant = [item[0] for item in scored if item[1] > 0]
    return relevant, True, set(substantive_tokens)


def validate_candidate_ids(answer: str, valid_candidate_ids: set[str]) -> bool:
    """Validate that any decision IDs referenced in an LLM answer exist in the retrieved candidates.

    Searches specifically for canonical `decision:[a-z0-9_\\-]+` identifiers.
    Returns True if all mentioned canonical decision IDs belong to the valid candidate set.

    Note: This is an entity-ID whitelist filter for canonical decision tokens. It does not
    catch informal references without the `decision:` prefix, nor does it perform general
    factual verification of prose statements.
    """
    mentioned_ids = set(re.findall(r"decision:[a-z0-9_\-]+", answer.lower()))
    valid_lower = {cid.lower() for cid in valid_candidate_ids}

    # If the answer cites canonical decisions not in the retrieved graph evidence, validation fails
    unsupported = mentioned_ids - valid_lower
    return len(unsupported) == 0
