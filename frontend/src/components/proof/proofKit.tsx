import { ApiError } from "../../lib/api";
import { routeApi } from "../agents/testHarness";
import { statusFor } from "../mode/modeKit";
import { rawProof, type Scenario } from "./proofFixtures";

type Answers = Record<string, unknown>;

export const PROOF_URL = "GET /api/v2/shariah/stocks/TCS/proof";

/** The engine as the proof screen sees it: the app's mode, and the proof for TCS. Anything else is refused. */
export function proofEngine(shariah: boolean, proof: Scenario | Record<string, unknown>, more: Answers = {}) {
  const body = typeof proof === "string" ? rawProof(proof) : proof;
  routeApi({ "GET /api/v2/status": statusFor(shariah), [PROOF_URL]: body, ...more });
}

export function proofMissing(shariah: boolean, more: Answers = {}) {
  routeApi({
    "GET /api/v2/status": statusFor(shariah),
    [PROOF_URL]: () => {
      throw new ApiError("HTTP_404", "Not Found", 404);
    },
    ...more,
  });
}
