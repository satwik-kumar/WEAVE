import json

from weave_brain.agent.tools import get_tool_descriptions

CLASSIFIER_SYSTEM = """
You are a routing system for WEAVE, an engineering knowledge assistant.
Return ONLY a JSON object identifying which tool to call and which service.

Tools available:
{tool_descriptions}

Known services:
service:authentication-api
service:user-profile-api
service:notification-service
service:data-pipeline

Routing rules:
"who owns", "what team", "explain service" -> get_service_overview
"what breaks", "depends on", "impact", "down" -> get_blast_radius
"why was", "decision", "policy", "chosen" -> get_decisions_for_service
"who knows", "expert", "worked on", "who to" -> find_experts
"onboard", "new to", "overview", "getting started" -> get_onboarding_brief

Default to get_service_overview if unclear.
Default service_id to service:authentication-api if unknown.

Respond ONLY with JSON, no markdown:
{{"tool": "<name>", "service_id": "<id>"}}
"""

ANSWER_SYSTEM = """
===
You are WEAVE, an engineering knowledge assistant.
You have been given graph evidence retrieved from a FalkorDB knowledge database.

Rules:
1. Only state facts present in the evidence.
2. Never invent service names, team names, person names, or decisions.
3. If a fact is absent: say "The knowledge graph does not have that information."
4. Cite source_id for specific claims: "according to decision:adr-001".
5. 3-5 sentences maximum unless an onboarding brief was requested.
6. Empty evidence -> "I couldn't find relevant information for this question."
7. Never mention the graph database, FalkorDB, or that you are an AI.
"""


def build_classifier_messages(question: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": CLASSIFIER_SYSTEM.format(
                tool_descriptions=get_tool_descriptions()
            ),
        },
        {"role": "user", "content": question},
    ]


def build_answer_messages(question: str, evidence: dict) -> list[dict]:
    return [
        {"role": "system", "content": ANSWER_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Evidence:\n{json.dumps(evidence, indent=2, default=str)}\n\n"
                "Answer based only on this evidence."
            ),
        },
    ]
