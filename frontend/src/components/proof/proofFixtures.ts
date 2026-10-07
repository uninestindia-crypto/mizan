import { parseProof, type StockProof } from "../../lib/proof";
import data from "./proofFixtures.data.json";

// Real output of the engine's proof builder (tests/shariah/proof_fixtures.py), one entry per situation. The company is
// an invented "Example" one and the figures are the filing figures the engine's own tests use. Nothing here is a claim
// about a real company.
//
//   compliant       both standards pass, business passes
//   split           the market-value standard passes, the total-assets standard fails: questionable, with the reason
//   depends         one figure the filing does not break down lands either side of its limit
//   sector_segment  fails the business test on a segment in its filing
//   sector_name     fails the business test on its name
//   ratio_fail      debt over the limit on both standards
//   not_confirmed   the business could not be confirmed: capped at questionable
//   no_price        the market-value standard needs price history
//   stale           an old filing
//   sample          the hand-entered sample: no filing, no field names
//   sample_differs  a filing that disagrees with the old sample
//   not_screened    nothing held at all

export type Scenario = keyof typeof data;

export const SCENARIOS = Object.keys(data) as Scenario[];

/** The proof as the engine sends it. A fresh copy each time, so one test cannot change another's. */
export function rawProof(name: Scenario): Record<string, unknown> {
  return structuredClone(data[name]) as Record<string, unknown>;
}

export function proofOf(name: Scenario): StockProof {
  return parseProof(rawProof(name));
}

export interface StatusFixture {
  verdict: string;
  data_status: string;
  short: string;
  as_of: string | null;
}

/** The one-line status the badges use, derived from a proof the way the engine's status call would. */
export function statusRow(name: Scenario): StatusFixture {
  const p = proofOf(name);
  const asOf = p.filing?.period_end ?? null;
  return { verdict: p.verdict, data_status: p.data_status, short: p.headline.slice(0, 80), as_of: asOf };
}
