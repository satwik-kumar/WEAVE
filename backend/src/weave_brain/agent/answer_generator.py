import logging
from typing import Any

from weave_brain.agent.prompts import build_answer_messages
from weave_brain.agent.provider import LLMProvider
from weave_brain.agent.ranking import (
    get_linked_incident,
    get_supersedes_info,
    rank_decision_candidates,
    validate_candidate_ids,
)

logger = logging.getLogger(__name__)

EMPTY = (
    "The knowledge graph does not have enough information for this question. "
    "Try asking about the authentication service."
)


def synthesize_grounded_answer(
    question: str, evidence: dict[str, Any], tool_name: str | None = None
) -> str:
    """Synthesize a factual, grounded answer directly from graph tool evidence."""
    if not evidence or not isinstance(evidence, dict):
        return EMPTY

    # 1. Onboarding composite brief
    if tool_name == "get_onboarding_brief" or (
        "overview" in evidence and "blast_radius" in evidence
    ):
        overview_data = evidence.get("overview", {})
        svc = overview_data.get("service", {})
        svc_name = svc.get("title") or svc.get("id", "the service")
        team = overview_data.get("team", {})
        team_name = team.get("title") or team.get("id", "Unknown Team")

        lines = [
            f"### Onboarding Brief: {svc_name}",
            f"**Service ID**: `{svc.get('id', '')}`",
            f"**Owning Team**: {team_name}",
        ]
        if svc.get("properties", {}).get("description"):
            lines.append(f"**Description**: {svc['properties']['description']}")

        # Decisions
        decisions_data = evidence.get("decisions", {})
        decs = (
            decisions_data.get("decisions", [])
            if isinstance(decisions_data, dict)
            else decisions_data
        )
        if decs:
            lines.append("\n**Key Architecture Decisions**:")
            for d in decs[:3]:
                props = d.get("properties", {})
                rat = props.get("rationale") or d.get("rationale", "")
                stat = props.get("status") or d.get("status", "accepted")
                lines.append(f"- **{d.get('title', d.get('id'))}** ({stat}): {rat}")

        # Experts
        experts_data = evidence.get("experts", {})
        exps = (
            experts_data.get("experts", [])
            if isinstance(experts_data, dict)
            else experts_data
        )
        if exps:
            lines.append("\n**Top Experts**:")
            for ex in exps[:3]:
                role_str = ""
                if ex.get("roles"):
                    role_str = f" ({', '.join(ex['roles'])})"
                lines.append(
                    f"- {ex.get('title') or ex.get('name') or ex.get('id')}{role_str}"
                )

        # Blast radius
        blast_data = evidence.get("blast_radius", {})
        blast_items = []
        if isinstance(blast_data, dict):
            blast_items = blast_data.get("affected_services", []) or blast_data.get(
                "blast_radius", []
            )
        elif isinstance(blast_data, list):
            blast_items = blast_data
        if blast_items:
            lines.append(
                f"\n**Dependency Risk**: {len(blast_items)} downstream service(s) depend on this service."
            )
        else:
            lines.append(
                "\n**Dependency Risk**: No downstream dependent services found."
            )

        return "\n".join(lines)

    # 2. Service overview (check before decisions, since overview includes decisions)
    if tool_name == "get_service_overview" or (
        "service" in evidence and "team" in evidence
    ):
        svc = evidence.get("service", {})
        svc_name = svc.get("title") or svc.get("id", "The service")
        team = evidence.get("team")
        team_str = (
            f"owned by team **{team.get('title') or team.get('id')}**"
            if team
            else "with no assigned owner team"
        )
        repos = evidence.get("repositories", [])
        repo_str = (
            f"implemented in repository `{repos[0].get('id')}`"
            if repos
            else "with no linked repository"
        )

        parts = [
            f"**{svc_name}** (`{svc.get('id', '')}`) is {team_str} and {repo_str}."
        ]

        props = svc.get("properties", {})
        if props.get("description"):
            parts.append(f"Description: {props['description']}")
        if props.get("tech_stack"):
            parts.append(f"Tech stack: {props['tech_stack']}.")

        deps = evidence.get("dependencies", [])
        if deps:
            dep_names = [
                (d.get("title") or d.get("id")) if isinstance(d, dict) else str(d)
                for d in deps
            ]
            parts.append(f"Dependencies: {', '.join(dep_names)}.")

        dependents = evidence.get("dependents", [])
        if dependents:
            dep_names = [
                (d.get("title") or d.get("id")) if isinstance(d, dict) else str(d)
                for d in dependents
            ]
            parts.append(f"Depended upon by: {', '.join(dep_names)}.")

        decs = evidence.get("decisions", [])
        if decs:
            dec_names = [
                (d.get("title") or d.get("id")) if isinstance(d, dict) else str(d)
                for d in decs
            ]
            parts.append(f"Associated architectural decisions: {', '.join(dec_names)}.")

        return " ".join(parts)

    # 3. Blast radius
    if (
        tool_name == "get_blast_radius"
        or "affected_services" in evidence
        or "blast_radius" in evidence
    ):
        svc_id = evidence.get("service_id", "")
        # Resolve title if possible from graph nodes
        svc_title = svc_id
        for n in evidence.get("graph", {}).get("nodes", []):
            if isinstance(n, dict) and n.get("id") == svc_id:
                svc_title = n.get("title", svc_id)
                break

        items = evidence.get("affected_services", []) or evidence.get(
            "blast_radius", []
        )
        if not items:
            return (
                f"No dependent services found for {svc_title or 'the service'}. "
                "Outages will not cascade downstream."
            )

        target_display = (
            f"{svc_title} (`{svc_id}`)" if svc_id else svc_title or "the service"
        )
        lines = [
            f"If {target_display} goes down, "
            + f"{len(items)} downstream service(s) are impacted:"
        ]
        for it in items:
            it_name = it.get("title") or it.get("id", "Service")
            depth = it.get("depth", 1)
            owning_team = it.get("owning_team")
            team_str = (
                f", owned by {owning_team.get('title') or owning_team.get('id')}"
                if owning_team
                else ""
            )
            lines.append(
                f"- **{it_name}** (`{it.get('id', '')}`) at hop depth {depth}{team_str}"
            )
        return "\n".join(lines)

    # 4. Decisions for service
    if tool_name == "get_decisions_for_service" or "decisions" in evidence:
        svc_id = evidence.get("service_id", "")
        svc_title = svc_id
        for n in evidence.get("graph", {}).get("nodes", []):
            if isinstance(n, dict) and n.get("id") == svc_id:
                svc_title = n.get("title", svc_id)
                break

        decs = evidence.get("decisions", [])
        if not decs:
            return (
                f"No architectural decisions recorded for {svc_title or 'the service'}."
            )

        target_display = (
            f"{svc_title} (`{svc_id}`)" if svc_id else svc_title or "the service"
        )
        graph_dict = (
            evidence.get("graph") if isinstance(evidence.get("graph"), dict) else None
        )

        ranked, is_specific, matched_terms = rank_decision_candidates(
            question, decs, graph=graph_dict
        )

        if is_specific and not ranked:
            terms_str = " ".join(sorted(matched_terms))
            return (
                f"The knowledge graph does not have enough information for this question. "
                f"No architectural decisions matching '{terms_str}' were found for {target_display}."
            )

        target_decisions = ranked if is_specific else decs
        lines = [
            f"Relevant architectural decisions for {target_display}:"
            if is_specific
            else f"Architectural decisions for {target_display}:"
        ]
        for d in target_decisions:
            title = d.get("title") or d.get("id", "ADR")
            props = d.get("properties", {})
            status = props.get("status") or d.get("status", "accepted")
            rationale = props.get("rationale") or d.get("rationale", "")
            rat_str = f": {rationale}" if rationale else "."
            line = f"- **{title}** (status: `{status}`){rat_str}"

            inc = get_linked_incident(d, graph=graph_dict)
            if inc:
                inc_title = inc.get("title") or inc.get("id", "")
                inc_id = inc.get("id", "")
                inc_str = (
                    f" Motivated by {inc_title} (`{inc_id}`)."
                    if inc_id and inc_id != inc_title
                    else f" Motivated by {inc_title}."
                )
                line += inc_str

            older_id, newer_id = get_supersedes_info(d, graph=graph_dict)
            if older_id:
                line += f" Supersedes `{older_id}`."
            if newer_id:
                newer_dec = next(
                    (
                        x
                        for x in decs
                        if (
                            x.get("id")
                            if isinstance(x, dict)
                            else getattr(x, "id", None)
                        )
                        == newer_id
                    ),
                    None,
                )
                if newer_dec:
                    newer_title = (
                        newer_dec.get("title")
                        if isinstance(newer_dec, dict)
                        else getattr(newer_dec, "title", newer_id)
                    )
                    newer_props = (
                        newer_dec.get("properties", {})
                        if isinstance(newer_dec, dict)
                        else getattr(newer_dec, "properties", {})
                    )
                    newer_rat = (
                        newer_props.get("rationale")
                        if isinstance(newer_props, dict)
                        else getattr(newer_props, "rationale", "")
                    )
                    if not newer_rat and isinstance(newer_dec, dict):
                        newer_rat = newer_dec.get("rationale", "")
                    if newer_rat:
                        line += f" Superseded by **{newer_title}** (`{newer_id}`): {newer_rat}."
                    else:
                        line += f" Superseded by **{newer_title}** (`{newer_id}`)."
                else:
                    line += f" Superseded by `{newer_id}`."

            lines.append(line)
        return "\n".join(lines)

    # 5. Experts
    if tool_name == "find_experts" or "experts" in evidence:
        exps = evidence.get("experts", [])
        if not exps:
            return "No domain experts identified for this service in the graph."

        lines = ["Identified experts based on past project contributions:"]
        for ex in exps:
            name = ex.get("title") or ex.get("name") or ex.get("id", "Engineer")
            roles = ex.get("roles", [])
            role_str = f" as {', '.join(roles)}" if roles else ""
            proj = ex.get("project")
            proj_str = f" on {proj.get('title') or proj.get('id')}" if proj else ""
            lines.append(f"- **{name}** (`{ex.get('id', '')}`){role_str}{proj_str}")
        return "\n".join(lines)

    return EMPTY


def generate_answer(
    question: str,
    evidence: dict,
    provider: LLMProvider | None = None,
    tool_name: str | None = None,
    warnings: list[str] | None = None,
) -> str:
    if not evidence:
        logger.warning("Empty evidence for: %s", question)
        return EMPTY
    if provider is not None:
        try:
            llm_text = provider.complete(
                build_answer_messages(question, evidence)
            ).strip()

            # Validate decision candidate IDs if decisions were retrieved
            if tool_name == "get_decisions_for_service" or "decisions" in evidence:
                valid_ids = {
                    d.get("id")
                    for d in evidence.get("decisions", [])
                    if isinstance(d, dict) and d.get("id")
                }
                if valid_ids and not validate_candidate_ids(llm_text, valid_ids):
                    logger.warning(
                        "LLM answer cited unsupported decision IDs. Falling back to grounded synthesis."
                    )
                    if warnings is not None:
                        warnings.append(
                            "AI answer cited unsupported entities; used grounded fallback."
                        )
                    return synthesize_grounded_answer(
                        question, evidence, tool_name=tool_name
                    )

            return llm_text
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "LLM answer generation failed (%s), falling back to grounded synthesis",
                e,
            )
            if warnings is not None:
                warnings.append(
                    "AI answer generation unavailable; used grounded fallback."
                )
    return synthesize_grounded_answer(question, evidence, tool_name=tool_name)
