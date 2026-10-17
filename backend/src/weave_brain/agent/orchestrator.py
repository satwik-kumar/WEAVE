"""Read-only agent loop with bounded tools, evidence and graph aggregation."""

import re
import time

from fastapi import HTTPException
from pydantic import ValidationError

from weave_brain.agent.providers import ModelProvider, ProviderError, ProviderState
from weave_brain.agent.tools import ToolResult, execute_tool
from weave_brain.core.config import get_settings
from weave_brain.domain.models import ChatRequest, ChatResponse
from weave_brain.services.graph_service import GraphService, bounded_view


def followups(service_id: str | None) -> list[str]:
    if not service_id:
        return []
    return [
        f"Who owns {service_id}?",
        f"Why were the decisions for {service_id} made?",
        f"What breaks if {service_id} goes down?",
        f"Who are the experts for {service_id}?",
    ]


def aggregate(results: list[ToolResult]) -> ChatResponse:
    views = [r.graph for r in results if r.graph]
    graph = (
        bounded_view(
            {
                "nodes": [n.model_dump() for view in views for n in view.nodes],
                "edges": [e.model_dump() for view in views for e in view.edges],
                "root_node_ids": list(
                    dict.fromkeys(n for view in views for n in view.root_node_ids)
                ),
                "highlighted_path_ids": list(
                    dict.fromkeys(
                        e for view in views for e in view.highlighted_path_ids
                    )
                ),
                "truncated": any(view.truncated for view in views),
                "warning": " ".join(
                    dict.fromkeys(view.warning for view in views if view.warning)
                ),
            }
        )
        if views
        else None
    )
    evidence = list(
        {
            (e.source_id, e.title, tuple(e.relationship_path)): e
            for r in results
            for e in r.evidence
        }.values()
    )
    root = next(
        (n for view in views for n in view.root_node_ids if n.startswith("service:")),
        None,
    )
    return ChatResponse(
        answer="",
        evidence=evidence,
        graph=graph,
        highlighted_paths=[
            e.relationship_path for e in evidence if e.relationship_path
        ],
        related_entities=list(
            {n.id: n for r in results for n in r.related_entities}.values()
        )[:100],
        suggested_followups=followups(root),
        warnings=list(dict.fromkeys(w for r in results for w in r.warnings)),
        intent={
            "service_decisions": "decision_rationale",
            "find_experts": "expert_finder",
            "find_connection": "connection",
        }.get(results[-1].tool, results[-1].tool)
        if results
        else "no_results",
    )


def process_question(
    request: ChatRequest,
    service: GraphService | None = None,
    provider: ModelProvider | None = None,
) -> ChatResponse:
    graph_service = service or GraphService(get_settings())
    model = provider or ModelProvider(graph_service.settings)
    state = ProviderState(
        items=[{"role": "user", "content": request.question}]
        if graph_service.settings.llm_provider != "gemini"
        else [
            {
                "type": "user_input",
                "content": [{"type": "text", "text": request.question}],
            }
        ]
    )
    results: list[ToolResult] = []
    deadline = time.monotonic() + 25
    for step in range(5):
        if time.monotonic() >= deadline:
            raise ProviderError("Agent time budget exceeded.")
        reply = model.turn(
            state,
            first=step == 0,
            final=step == 4,
            timeout=max(0.1, deadline - time.monotonic()),
        )
        state = reply.state
        if not reply.calls:
            if not results:
                raise ProviderError(
                    "Model returned an answer without retrieving evidence."
                )
            response = aggregate(results)
            citations = {int(x) for x in re.findall(r"\[S(\d+)\]", reply.text)}
            if response.evidence and (
                not citations
                or any(x < 1 or x > len(response.evidence) for x in citations)
            ):
                raise ProviderError(
                    "Model response did not cite valid retrieved evidence."
                )
            ids = {n.id for n in response.graph.nodes} if response.graph else set()
            claimed = set(
                re.findall(
                    r"(?:service|team|person|decision|incident|ticket|repository|file|project|document|test):[a-z0-9][a-z0-9/._:-]*",
                    reply.text,
                )
            )
            claimed = {value.rstrip(".,:") for value in claimed}
            if claimed - ids or not reply.text.strip():
                raise ProviderError(
                    "Model response referenced entities that were not retrieved."
                )
            response.answer = reply.text
            response.warnings.append(
                "AI-generated synthesis from retrieved records. Each question is independent."
            )
            if graph_service.settings.development_fixtures:
                response.warnings.append(
                    "Development fixture data; no live database retrieval."
                )
            return response
        if len(results) + len(reply.calls) > 6 or step == 4:
            raise ProviderError("Agent tool budget exceeded.")
        for call in reply.calls:
            try:
                result = execute_tool(call.name, call.arguments, graph_service)
            except (ValueError, ValidationError):
                raise ProviderError(
                    "Model requested an invalid or unregistered tool."
                ) from None
            except HTTPException as error:
                if error.status_code >= 500:
                    raise
                result = ToolResult(
                    tool=call.name,
                    summary="No matching entity or valid query was retrieved.",
                )
            results.append(result)
            combined = aggregate(results)
            numbered = "\n".join(
                f"[S{i + 1}] {e.title} ({e.source_id}): {e.excerpt or ''}"
                for i, e in enumerate(combined.evidence)
            )
            payload = (
                result.model_dump_json() + "\nCurrent source numbering:\n" + numbered
            )
            if len(payload) > 100000:
                raise ProviderError(
                    "Retrieved context exceeds the bounded model context."
                )
            state = model.add_result(state, call, payload)
    raise ProviderError("Agent tool budget exceeded.")
