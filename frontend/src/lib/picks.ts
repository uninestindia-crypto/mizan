// The note the platform attaches when it asks for a second opinion on a stock its own rules chose.
// It is shown to the AI models in the "told the pick" question (to measure anchoring), so it states where the stock
// came from and nothing that sounds like a recommendation or a promise.

const MAX_NOTE_CHARS = 300;

export type PaperPickKind = "holding" | "queued_buy" | "queued_sell";

const PAPER_WORDS: Record<PaperPickKind, string> = {
  holding: "currently held by",
  queued_buy: "queued to be bought by",
  queued_sell: "queued to be sold by",
};

const CLOSING = "This is a rule's selection in a system test, not evidence the stock will do well.";
const BASKET_CLOSING =
  "It is a list in the app's sample data, not a recommendation, and a stock on it " +
  "is not necessarily Shariah-compliant.";

function clip(text: string): string {
  return text.length <= MAX_NOTE_CHARS ? text : `${text.slice(0, MAX_NOTE_CHARS - 1).trimEnd()}…`;
}

function plain(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

/** A stock a paper book holds or has queued, chosen by that book's own rule. */
export function paperBookPickNote(bookName: string, symbol: string, kind: PaperPickKind): string {
  const book = plain(bookName) || "this paper book";
  const lead = `${plain(symbol).toUpperCase()} is ${PAPER_WORDS[kind]} the paper book "${book}", by that book's rule.`;
  return clip(`${lead} ${CLOSING}`);
}

/** A stock listed in one of the halal baskets. */
export function basketPickNote(basketName: string, symbol: string): string {
  const basket = plain(basketName) || "this";
  const lead = `${plain(symbol).toUpperCase()} is listed in the "${basket}" basket.`;
  return clip(`${lead} ${BASKET_CLOSING}`);
}
