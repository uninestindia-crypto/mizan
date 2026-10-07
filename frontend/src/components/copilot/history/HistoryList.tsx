import type { UseQueryResult } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import type { ChatSummary } from "../../../lib/copilotHistory";
import { Button, Callout, Skeleton } from "../../ui";
import { ChatRow, type RowContext } from "./ChatRow";

export const NO_CHATS = "No saved chats yet. Ask the Copilot something and it will appear here.";
export const NO_MATCH = "No chat matches that.";

function Loading() {
  return (
    <div role="status" className="space-y-2 px-1 py-1">
      <span className="sr-only">Loading your chats</span>
      {[0, 1, 2].map((n) => (
        <Skeleton key={n} className="h-[68px] w-full rounded-xl" />
      ))}
    </div>
  );
}

function Empty({ searching }: { searching: boolean }) {
  return <p className="px-3 py-8 text-center text-[13.5px] text-ink-2">{searching ? NO_MATCH : NO_CHATS}</p>;
}

function Problem({ retry }: { retry: () => void }) {
  const action = (
    <Button size="sm" variant="secondary" onClick={retry}>
      Try again
    </Button>
  );
  return (
    <Callout tone="warn" action={action}>
      Your chats could not be loaded just now.
    </Callout>
  );
}

interface HistoryListProps {
  list: UseQueryResult<ChatSummary[]>;
  searching: boolean;
  context: RowContext;
}

/** The saved chats as a list, or the plain sentence for why there is none to show. */
export function HistoryList({ list, searching, context }: HistoryListProps) {
  const chats = list.data;
  if (!chats) return list.isError ? <Problem retry={() => void list.refetch()} /> : <Loading />;
  if (chats.length === 0) return <Empty searching={searching} />;
  const shown = `${chats.length} ${chats.length === 1 ? "chat" : "chats"} shown`;
  return (
    <>
      <p role="status" className="sr-only">
        {shown}
      </p>
      <ul aria-label="Your saved chats" className="space-y-1">
        {chats.map((chat) => (
          <ChatRow key={chat.id} chat={chat} context={context} />
        ))}
      </ul>
      {list.isFetching && <Loader2 className="mx-auto mt-2 size-4 animate-spin text-ink-3" aria-hidden />}
    </>
  );
}
