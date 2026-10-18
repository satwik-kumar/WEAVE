import { lazy, Suspense, useEffect, useState, useRef } from "react";
import { useGraphStore } from "../store/graphStore";
import { useChatStore } from "../store/chatStore";
import { Icon } from "../components/Icon";
import { BrainAnswer } from "../components/chat/BrainAnswer";

const GraphCanvas = lazy(() =>
  import("../components/graph/GraphCanvas").then((module) => ({
    default: module.GraphCanvas,
  })),
);

const questions = [
  "Who owns the authentication service?",
  "What breaks if the authentication service goes down?",
  "Why do authentication tokens expire?",
  "Who are the authentication experts?",
  "What is the change impact of authentication?",
];

export function AskBrainPage() {
  useEffect(() => {
    useGraphStore.getState().setContext("ask");
    const last = useChatStore.getState().messages.at(-1);
    if (last)
      useGraphStore
        .getState()
        .replace(
          last.response.graph,
          last.response.intent,
          last.response.highlighted_paths,
        );
  }, []);
  const [text, setText] = useState("");
  const { messages, loading, error, lastQuestion, submitQuestion } =
    useChatStore();
  const conversation = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = conversation.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      const { loading, error } = useChatStore.getState();
      if (loading || error) element.scrollTop = element.scrollHeight;
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const element = conversation.current;
    const turn = element?.querySelector<HTMLElement>(
      ".conversation-turn:last-of-type",
    );
    if (element && turn)
      element.scrollTop +=
        turn.getBoundingClientRect().top - element.getBoundingClientRect().top;
  }, [messages.length]);
  useEffect(() => {
    if ((loading || error) && conversation.current)
      conversation.current.scrollTop = conversation.current.scrollHeight;
  }, [loading, error]);
  return (
    <main className="workspace">
      <section className="chat-panel">
        <div className="panel-heading">
          <div>
            <h1>Ask Brain</h1>
          </div>
          <span className="badge">
            <Icon name="graph" size={13} /> Evidence-backed
          </span>
        </div>
        <div className="conversation" aria-live="polite" ref={conversation}>
          {!messages.length && (
            <div className="welcome">
              <div className="brain-mark">
                <Icon name="chat" size={24} />
              </div>
              <h2>
                Less searching.
                <br />
                More understanding.
              </h2>
              <p>
                Explore ownership, decisions and dependencies through connected
                evidence.
              </p>
              <h3>Start with a question</h3>
              {questions.map((q) => (
                <button
                  disabled={loading}
                  onClick={() => void submitQuestion(q)}
                  key={q}
                >
                  {q}
                  <Icon name="arrow" size={16} />
                </button>
              ))}
              <p className="muted">
                Each question retrieves records independently.
              </p>
            </div>
          )}
          {messages.map((m) => (
            <div className="conversation-turn" key={m.response.message_id}>
              <p className="user-message">{m.question}</p>
              <BrainAnswer response={m.response} />
            </div>
          ))}
          {loading && (
            <div role="status" className="loading">
              Retrieving connected evidence…
            </div>
          )}
          {error && (
            <div role="alert" className="error">
              {error}
              {lastQuestion && (
                <button
                  disabled={loading}
                  onClick={() => void submitQuestion(lastQuestion)}
                >
                  Retry
                </button>
              )}
            </div>
          )}
        </div>
        <form
          className="question-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (!loading && text.trim()) {
              void submitQuestion(text);
              setText("");
            }
          }}
        >
          <label htmlFor="question">Ask about your engineering knowledge</label>
          <div>
            <textarea
              id="question"
              rows={2}
              maxLength={4000}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Who owns authentication?"
              disabled={loading}
            />
            <button
              aria-label="Ask ↗"
              disabled={loading || !text.trim()}
              type="submit"
            >
              <span>{loading ? "Asking..." : "Ask"}</span>
              <Icon name="arrow" size={17} />
            </button>
          </div>
          <small>
            Answers reflect only retrieved records. No conversation memory.
          </small>
        </form>
      </section>
      <Suspense
        fallback={
          <section className="graph-panel">
            <div className="panel-heading">
              <h2>Evidence graph</h2>
            </div>
            <div className="canvas">
              <p role="status" className="canvas-empty">
                Loading graph canvas…
              </p>
            </div>
          </section>
        }
      >
        <GraphCanvas />
      </Suspense>
    </main>
  );
}
