"""Public retrieval completeness and source attribution regressions."""

from weave_brain.graph.queries import get_blast_radius


def test_query_limit_surfaces_omitted_rows_without_unbounded_output():
    class Result:
        def __init__(self, rows):
            self.result_set = rows

    class Graph:
        def query(self, cypher, _params):
            if "RETURN path" in cypher:
                assert "LIMIT 51" in cypher
                return Result([[None]] * 51)
            return Result(
                [
                    [
                        {
                            "id": "service:authentication-api",
                            "type": "service",
                            "title": "Auth",
                        }
                    ]
                ]
            )

    result = get_blast_radius("service:authentication-api", graph=Graph())
    assert result["graph"]["truncated"] is True
    assert result["graph"]["warning"]
    assert len(result["graph"]["nodes"]) <= 100
