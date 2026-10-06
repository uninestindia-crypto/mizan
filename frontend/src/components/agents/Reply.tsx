import { Fragment, useMemo } from "react";
import { friendlyDates } from "../../lib/plainDates";
import { type Block, hostOf, type Inline, parseReply } from "./replyMarkdown";

// A reply from an agent, drawn as plain React elements. Nothing here ever inserts HTML.

const LINK_CLASS = "font-medium text-brand underline";

function InlineView({ node }: { node: Inline }) {
  if (node.kind === "bold") return <strong className="font-semibold text-ink">{friendlyDates(node.text)}</strong>;
  if (node.kind === "text") return <>{friendlyDates(node.text)}</>;
  return (
    <>
      <a href={node.href} title={node.href} target="_blank" rel="noopener noreferrer" className={LINK_CLASS}>
        {friendlyDates(node.text)}
      </a>
      <span className="text-ink-3"> ({hostOf(node.href)})</span>
    </>
  );
}

function Inlines({ nodes }: { nodes: Inline[] }) {
  return (
    <>
      {nodes.map((node, i) => (
        <InlineView key={i} node={node} />
      ))}
    </>
  );
}

function ListView({ items }: { items: Inline[][] }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((item, i) => (
        <li key={i}>
          <Inlines nodes={item} />
        </li>
      ))}
    </ul>
  );
}

function ParagraphView({ lines }: { lines: Inline[][] }) {
  return (
    <p>
      {lines.map((line, i) => (
        <Fragment key={i}>
          {i > 0 && <br />}
          <Inlines nodes={line} />
        </Fragment>
      ))}
    </p>
  );
}

function BlockView({ block }: { block: Block }) {
  if (block.kind === "list") return <ListView items={block.items} />;
  if (block.kind === "paragraph") return <ParagraphView lines={block.lines} />;
  return (
    <p className="font-semibold text-ink">
      <Inlines nodes={block.content} />
    </p>
  );
}

export function Reply({ text }: { text: string }) {
  const blocks = useMemo(() => parseReply(text), [text]);
  return (
    <div className="space-y-2 break-words text-sm leading-relaxed text-ink-2">
      {blocks.map((block, i) => (
        <BlockView key={i} block={block} />
      ))}
    </div>
  );
}
