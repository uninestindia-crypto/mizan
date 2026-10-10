import type { ProofTest, TestResult } from "../../lib/proof";
import { limitPercent, percent } from "./proofFormat";

const FILL: Record<TestResult, string> = {
  PASS: "bg-up",
  FAIL: "bg-down",
  BORDERLINE: "bg-warn",
  DEPENDS: "bg-warn",
  NOT_COMPUTED: "bg-ink-3",
};

// A thin bar from zero. The solid part is the lower reading, the hatched part runs on to the upper reading, and the
// upright line is the limit. The numbers and the result are written beside it, so the bar is never the only signal.
const HATCH = "repeating-linear-gradient(135deg, currentColor 0 2px, transparent 2px 5px)";

function share(value: number, scale: number): number {
  return Math.max(0, Math.min(100, (value / scale) * 100));
}

function Bars({ test, scale }: { test: ProofTest; scale: number }) {
  const low = test.low?.pct ?? 0;
  const top = Math.max(low, test.high?.pct ?? 0);
  const fill = { width: `${share(low, scale)}%` };
  const reach = { left: `${share(low, scale)}%`, width: `${share(top - low, scale)}%`, backgroundImage: HATCH };
  return (
    <div className="absolute inset-x-0 top-1/2 h-2 -translate-y-1/2 overflow-hidden rounded-full bg-surface-3">
      <div className={`absolute inset-y-0 left-0 ${FILL[test.result]}`} style={fill} />
      {top > low && <div className="absolute inset-y-0 opacity-70" style={reach} />}
    </div>
  );
}

export function LimitBar({ test }: { test: ProofTest }) {
  const low = test.low?.pct;
  const high = test.high?.pct;
  const limit = test.limit_pct;
  if (typeof low !== "number" || typeof high !== "number" || limit === null) return null;
  const top = Math.max(low, high);
  const scale = Math.max(limit * 1.25, top * 1.08, 1);
  const range = top > low ? ` to ${percent(top)}` : "";
  const label = `${percent(low)}${range} against a limit of ${limitPercent(limit)}`;
  return (
    <div role="img" aria-label={label} className="relative h-4 w-full text-warn">
      <Bars test={test} scale={scale} />
      <div className="absolute inset-y-0 w-0.5 -translate-x-1/2 bg-ink" style={{ left: `${share(limit, scale)}%` }} />
    </div>
  );
}
