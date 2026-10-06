import { Fragment, useMemo } from "react";
import { cx } from "../ui";
import { type Inline, parseMarkdown } from "./markdown";

type LinkNode = Extract<Inline, { type: "link" }>;

const LINK_STYLE = "font-medium text-brand underline underline-offset-2";

/** A link opens in a new tab without handing over this page, and always shows where it really goes. */
function LinkView({ node }: { node: LinkNode }) {
  return (
    <>
      <a href={node.href} target="_blank" rel="noopener noreferrer" className={LINK_STYLE}>
        {node.text}
      </a>
      <span className="text-[12px] text-ink-3"> ({node.host})</span>
    </>
  );
}

function InlineNode({ node }: { node: Inline }) {
  switch (node.type) {
    case "text":
      return <Fragment>{node.text}</Fragment>;
    case "break":
      return <br />;
    case "bold":
      return (
        <strong className="font-semibold">
          <InlineNodes nodes={node.children} />
        </strong>
      );
    case "link":
      return <LinkView node={node} />;
  }
}

function InlineNodes({ nodes }: { nodes: readonly Inline[] }) {
  return (
    <>
      {nodes.map((node, index) => (
        <InlineNode key={index} node={node} />
      ))}
    </>
  );
}

function ListBlock({ items }: { items: readonly (readonly Inline[])[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((item, index) => (
        <li key={index}>
          <InlineNodes nodes={item} />
        </li>
      ))}
    </ul>
  );
}

/** A reply, drawn from the safe tree. Text is always inserted as text; no markup from the reply is ever used. */
export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  return (
    <div className={cx("space-y-2 break-words text-[13.5px] leading-relaxed text-ink", className)}>
      {blocks.map((block, index) =>
        block.type === "list" ? (
          <ListBlock key={index} items={block.items} />
        ) : (
          <p key={index}>
            <InlineNodes nodes={block.children} />
          </p>
        ),
      )}
    </div>
  );
}
