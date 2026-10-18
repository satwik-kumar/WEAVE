import { Icon } from "../Icon";
import { SuggestedFollowups } from "./SuggestedFollowups";
import { useChatStore } from "../../store/chatStore";
import Markdown from "react-markdown";
import type { ChatResponse } from "../../types/api";
import { EvidenceList } from "./EvidenceList";
import { safeUrl } from "../../api/safeUrl";
import { CopyButton } from "../CopyButton";

export function BrainAnswer({ response }: { response: ChatResponse }) {
  return (
    <article className="brain-answer">
      <div className="answer-label">
        <span className="answer-avatar">
          <Icon name="brain" size={16} />
        </span>{" "}
        WEAVE <span>Source-backed answer</span>
      </div>
      <div className="answer-body">
        <Markdown
          skipHtml
          components={{
            a: ({ href, children }) =>
              safeUrl(href) ? (
                <a href={safeUrl(href)} target="_blank" rel="noreferrer">
                  {children}
                </a>
              ) : (
                <span>{children}</span>
              ),
          }}
        >
          {response.answer}
        </Markdown>
      </div>
      <div className="answer-actions">
        <CopyButton text={response.answer} label="Copy answer" />
      </div>
      {(response.warnings ?? []).map((warning, i) => (
        <p className="notice" key={i}>
          {warning}
        </p>
      ))}
      <EvidenceList evidence={response.evidence ?? []} graph={response.graph} />
      <SuggestedFollowups
        suggestions={response.suggested_followups ?? []}
        onSelect={(question) =>
          void useChatStore.getState().submitQuestion(question)
        }
        disabled={useChatStore((state) => state.loading)}
      />
    </article>
  );
}
