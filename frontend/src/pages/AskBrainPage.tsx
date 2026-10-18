import {
  lazy,
  Suspense,
  useEffect,
  useLayoutEffect,
  useState,
  useRef,
} from "react";
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
  const {
    draft: text,
    setDraft: setText,
    messages,
    loading,
    error,
    lastQuestion,
    submitQuestion,
  } = useChatStore();
  const conversation = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  useLayoutEffect(() => {
    const field = input.current;
    if (!field) return;
    field.style.height = "auto";
    field.style.height = `${Math.min(field.scrollHeight, 160)}px`;
  }, [text]);
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "/") {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
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
            <small className="eyebrow">YOUR ENGINEERING KNOWLEDGE</small>
            <h1>Ask Brain</h1>
          </div>
          <span className="badge">
            <Icon name="graph" size={13} /> Evidence-backed
          </span>
        </div>
        <div
          className="conversation"
          aria-live="polite"
          ref={conversation}
          onScroll={(event) => {
            const element = event.currentTarget;
            setAtBottom(
              element.scrollHeight - element.scrollTop - element.clientHeight <
                80,
            );
          }}
        >
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
              <h3>Explore a starting point</h3>
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
            <div className="pending-turn">
              <p className="user-message">{lastQuestion}</p>
              <div role="status" className="loading">
                Retrieving connected evidence…
              </div>
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
        {!atBottom && messages.length > 0 && (
          <button
            className="latest-answer"
            onClick={() => {
              conversation.current?.scrollTo({
                top: conversation.current.scrollHeight,
              });
            }}
          >
            Jump to latest <Icon name="arrow" size={14} />
          </button>
        )}
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
              ref={input}
              rows={2}
              maxLength={4000}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing &&
                  event.nativeEvent.keyCode !== 229
                ) {
                  event.preventDefault();
                  if (!event.repeat) event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder="Who owns authentication?"
              disabled={loading}
              enterKeyHint="send"
              aria-describedby="question-help"
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
          <small id="question-help">
            <span>
              Enter to send <span aria-hidden="true">·</span> Shift+Enter for a
              new line
            </span>
            <span>No conversation memory</span>
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
