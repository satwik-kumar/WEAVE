import { useEffect, useId, useRef, useState } from "react";
import type { GraphNode } from "../../types/api";
import { Icon } from "../Icon";
import { colors } from "./colors";

export function EntityFinder({
  nodes,
  onChoose,
}: {
  nodes: GraphNode[];
  onChoose: (id: string) => void;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const matches = nodes.filter((node) =>
    `${node.title} ${node.id}`
      .toLocaleLowerCase()
      .includes(query.trim().toLocaleLowerCase()),
  );
  const results = matches.slice(0, 12);
  useEffect(() => {
    if (!open) return;
    const option = document.getElementById(`${id}-${active}`);
    const popover = list.current;
    if (option && popover) {
      if (option.offsetTop < popover.scrollTop)
        popover.scrollTop = option.offsetTop;
      else if (
        option.offsetTop + option.offsetHeight >
        popover.scrollTop + popover.clientHeight
      )
        popover.scrollTop =
          option.offsetTop + option.offsetHeight - popover.clientHeight;
    }
  }, [active, open, id, query]);
  const choose = (node: GraphNode) => {
    setOpen(false);
    setQuery("");
    setActive(0);
    onChoose(node.id);
    input.current?.blur();
  };
  return (
    <div
      className="entity-finder"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <Icon name="search" size={15} />
      <input
        ref={input}
        type="text"
        role="combobox"
        aria-label="Find graph entity"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-controls={open ? id : undefined}
        aria-activedescendant={
          open && results.length
            ? `${id}-${Math.min(active, results.length - 1)}`
            : undefined
        }
        placeholder="Find an entity…"
        value={query}
        autoComplete="off"
        spellCheck={false}
        disabled={!nodes.length}
        onFocus={() => setOpen(true)}
        onChange={(event) => {
          setQuery(event.target.value);
          setActive(0);
          setOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.stopPropagation();
            setOpen(false);
          }
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
            setActive((value) =>
              Math.max(
                0,
                Math.min(
                  results.length - 1,
                  value + (event.key === "ArrowDown" ? 1 : -1),
                ),
              ),
            );
          }
          if (
            event.key === "Enter" &&
            results.length &&
            open &&
            !event.nativeEvent.isComposing
          ) {
            event.preventDefault();
            choose(results[Math.min(active, results.length - 1)]);
          }
        }}
      />
      {query && (
        <button
          type="button"
          className="finder-clear icon-button"
          aria-label="Clear entity search"
          onClick={() => {
            setQuery("");
            setActive(0);
            input.current?.focus();
          }}
        >
          <Icon name="close" size={13} />
        </button>
      )}
      {open && (
        <div className="finder-popover" ref={list}>
          <div className="finder-caption">
            {query
              ? `${matches.length} matching ${matches.length === 1 ? "entity" : "entities"}`
              : "ENTITIES IN THIS GRAPH"}
          </div>
          <div role="listbox" id={id} aria-label="Graph entities">
            {results.map((node, index) => (
              <div
                role="option"
                id={`${id}-${index}`}
                key={node.id}
                aria-selected={index === active}
                onPointerMove={() => setActive(index)}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(node)}
                className="finder-option"
              >
                <Icon
                  name={node.type}
                  size={16}
                  style={{ color: colors[node.type] }}
                />
                <span>
                  <strong>{node.title}</strong>
                  <small>
                    {node.type} · {node.id}
                  </small>
                </span>
                <Icon name="arrow" size={14} />
              </div>
            ))}
          </div>
          {!results.length && (
            <p className="finder-empty">
              No entities match “{query}”. Try a name or ID.
            </p>
          )}
          {matches.length > 12 && (
            <p className="finder-empty">
              Showing 12 of {matches.length}. Type to narrow the list.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
