import { beforeEach, describe, expect, it, vi } from "vitest";
import type { GraphView } from "../types/api";
import { cleanGraph, mergeGraph, useGraphStore } from "./graphStore";
import { useChatStore } from "./chatStore";
import { safeUrl } from "../api/safeUrl";

const graph: GraphView = {
  nodes: [
    {
      id: "service:a",
      type: "service",
      title: "A",
      properties: {},
      on_highlighted_path: false,
    },
  ],
  edges: [],
  root_node_ids: ["service:a"],
  highlighted_path_ids: [],
  truncated: false,
};
beforeEach(() => {
  useGraphStore.getState().setContext("ask");
  useGraphStore.getState().replace(null);
  useChatStore.setState({
    messages: [],
    loading: false,
    error: "",
    lastQuestion: "",
  });
  vi.restoreAllMocks();
});
describe("graph state", () => {
  it("deduplicates expansion and removes invalid endpoints without fabricating nodes", () => {
    expect(mergeGraph(graph, graph).nodes).toHaveLength(1);
    const full = {
      ...graph,
      nodes: Array.from({ length: 100 }, (_, i) => ({
        ...graph.nodes[0],
        id: `service:${i}`,
      })),
    };
    expect(mergeGraph(full, full).truncated).toBe(false);
    const result = cleanGraph({
      ...graph,
      edges: [
        {
          id: "e",
          source_id: "service:a",
          target_id: "service:missing",
          relationship_type: "DEPENDS_ON",
          label: "DEPENDS_ON",
          properties: {},
        },
      ],
    });
    expect(result.edges).toHaveLength(0);
    expect(result.warning).toContain("missing endpoints");
  });
  it("ignores expansion from a previous question", () => {
    const version = useGraphStore.getState().version;
    useGraphStore.getState().replace(null);
    useGraphStore.getState().merge(graph, version);
    expect(useGraphStore.getState().graph.nodes).toHaveLength(0);
  });
  it("honors node limits and null graphs", () => {
    const result = cleanGraph({
      ...graph,
      nodes: Array.from({ length: 110 }, (_, i) => ({
        ...graph.nodes[0],
        id: `service:${i}`,
      })),
    });
    expect(result.nodes).toHaveLength(100);
    expect(result.truncated).toBe(true);
    useGraphStore.getState().replace(null);
    expect(useGraphStore.getState().graph.nodes).toHaveLength(0);
  });
  it("highlights only consecutive evidence edges, preserving directions", () => {
    const nodes = ["a", "b", "c"].map((id) => ({
      ...graph.nodes[0],
      id: `service:${id}`,
    }));
    const edges = [
      ["a", "b"],
      ["b", "c"],
      ["a", "c"],
    ].map(([a, b]) => ({
      id: `${a}-${b}`,
      source_id: `service:${a}`,
      target_id: `service:${b}`,
      relationship_type: "DEPENDS_ON",
      label: "DEPENDS_ON",
      properties: {},
    }));
    useGraphStore
      .getState()
      .replace({ ...graph, nodes, edges }, null, [
        ["service:a", "service:b", "service:c"],
      ]);
    expect([...useGraphStore.getState().focusEdges]).toEqual(["a-b", "b-c"]);
  });
});
describe("chat state", () => {
  it("retains a completed answer without overwriting a report graph after navigation", async () => {
    let resolve!: (response: Response) => void;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const pending = useChatStore.getState().submitQuestion("auth");
    useGraphStore.getState().setContext("health");
    useGraphStore.getState().replace(null);
    resolve(
      new Response(
        JSON.stringify({
          message_id: "late",
          answer: "Completed",
          graph,
          evidence: [],
          warnings: [],
        }),
      ),
    );
    await pending;
    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useGraphStore.getState().graph.nodes).toHaveLength(0);
  });
  it("serializes duplicate submissions and updates response and graph", async () => {
    let resolve!: (value: Response) => void;
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r;
        }),
    );
    const first = useChatStore
      .getState()
      .submitQuestion("Who owns authentication?");
    await useChatStore.getState().submitQuestion("duplicate");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(useChatStore.getState().loading).toBe(true);
    resolve(
      new Response(
        JSON.stringify({
          message_id: "m1",
          answer: "Grounded",
          graph,
          evidence: [],
          warnings: [],
          intent: null,
        }),
      ),
    );
    await first;
    expect(useChatStore.getState().loading).toBe(false);
    expect(useChatStore.getState().messages[0].response.answer).toBe(
      "Grounded",
    );
    expect(useGraphStore.getState().graph.nodes[0].id).toBe("service:a");
  });
  it("preserves prior graph and conversation on failure then retries", async () => {
    useGraphStore.getState().replace(graph);
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("", { status: 503 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            message_id: "m2",
            answer: "Recovered",
            graph: null,
            evidence: [],
            warnings: [],
          }),
        ),
      );
    await useChatStore.getState().submitQuestion("auth");
    expect(useChatStore.getState().error).toContain("unavailable");
    expect(useGraphStore.getState().graph.nodes).toHaveLength(1);
    expect(useChatStore.getState().loading).toBe(false);
    await useChatStore.getState().submitQuestion("auth");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(useChatStore.getState().messages).toHaveLength(1);
    expect(useGraphStore.getState().graph.nodes).toHaveLength(0);
  });
});
it("allows only safe source links", () => {
  expect(safeUrl("javascript:alert(1)")).toBeUndefined();
  expect(safeUrl("https://user:password@example.com")).toBeUndefined();
  expect(safeUrl("https://example.com/source")).toBe(
    "https://example.com/source",
  );
});
