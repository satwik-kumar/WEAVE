# Grounding evaluation

The local seed is synthetic company data. Evaluate deterministic retrieval separately from model synthesis.

| Question | Required grounding |
| --- | --- |
| Who owns authentication? | Platform Engineering; Team → OWNS → Service; actual authentication repository and source IDs. |
| Why do tokens expire? | ADR-001 rationale and INC-007 through MOTIVATED_BY; no duplicated invented source. |
| What breaks if authentication goes down? | Incoming DEPENDS_ON paths; User Profile and Notification, excluding unrelated Data Pipeline. |
| Who are authentication experts? | Actual Priya/James records with Person → WORKED_ON → Project → USES → Service evidence. |
| Change impact? | Only retrieved dependents/decisions/incidents/tickets/files/tests; no invented code or test coverage. |
| Onboarding? | Accepted non-superseded decisions, actual experts/risks, directly linked open incidents and tickets. |
| Knowledge health? | Recorded gap metrics, including unowned Data Pipeline; bounded gap warnings. |

`backend/tests/unit/test_reports_agent.py` checks provider protocol roundtrips using mocked HTTP transports, whitelist/argument validation, citation identifiers, unknown IDs, failures and tool-call budget. It does not prove successful paid-model execution or semantic entailment.

`frontend/tests/browser/live.spec.ts` uses the actual seeded FalkorDB. The default browser suite explicitly uses fixtures. Full backend integration tests use isolated UUID-named graphs. Actual closed-port failure/recovery and live acceptance output are recorded in [full-scope-checks.txt](full-scope-checks.txt). No LLM credentials were available, so live model quality remains NOT RUN.
