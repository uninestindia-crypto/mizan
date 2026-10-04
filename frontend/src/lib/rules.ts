// The limits the engine enforces on a person's money rules, stated up front so nobody has to find
// them by pressing Continue and reading a developer error. Keep in step with MoneyRules in
// src/quant_system/server/v2/state.py.

export const MONEY_LIMITS = {
  capitalMin: 1_000,
  capitalMax: 10_000_000_000,
  riskMax: 10,
  dailyMax: 20,
} as const;

export interface MoneyProblems {
  capital?: string;
  risk?: string;
  daily?: string;
}

const rupees = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export function moneyProblems(capital: string, risk: string, daily: string): MoneyProblems {
  const out: MoneyProblems = {};
  const c = Number(capital);
  if (!capital.trim() || !Number.isFinite(c)) out.capital = "Enter a number.";
  else if (c < MONEY_LIMITS.capitalMin) out.capital = `Enter at least ${rupees(MONEY_LIMITS.capitalMin)}.`;
  else if (c > MONEY_LIMITS.capitalMax) out.capital = `That is more than QuantOS supports (${rupees(MONEY_LIMITS.capitalMax)}).`;
  const r = Number(risk);
  if (!risk.trim() || !Number.isFinite(r) || r <= 0) out.risk = "Enter more than 0%.";
  else if (r > MONEY_LIMITS.riskMax) out.risk = `Enter ${MONEY_LIMITS.riskMax}% or less. Risking more per trade is how accounts blow up.`;
  const d = Number(daily);
  if (!daily.trim() || !Number.isFinite(d) || d <= 0) out.daily = "Enter more than 0%.";
  else if (d > MONEY_LIMITS.dailyMax) out.daily = `Enter ${MONEY_LIMITS.dailyMax}% or less.`;
  return out;
}

const FIELD_LABELS: Record<string, string> = {
  "money.capital": "Money you trade with",
  "money.risk_per_trade_pct": "Risk per trade",
  "money.daily_loss_limit_pct": "Daily loss limit",
  "broker.delivery_per_order": "Delivery brokerage",
  "broker.intraday_per_order": "Intraday brokerage",
  "broker.fno_per_order": "F&O brokerage",
  "broker.dp_charge_per_sell": "DP charge per sell",
  capital: "Starting capital",
  slippage_bps: "Slippage",
  start: "Start date",
  end: "End date",
  symbols: "Stocks",
};

/** Turn "money.capital: Input should be greater than or equal to 1000" into a sentence a person can act on. */
export function plainValidation(field: string, message: string): string {
  const label = FIELD_LABELS[field] ?? field.split(".").pop()?.replace(/_/g, " ") ?? "This field";
  const number = /(-?[\d.]+)$/.exec(message)?.[1];
  const shown = number ? Number(number).toLocaleString("en-IN") : "";
  let reason = message;
  if (/valid (decimal|number|integer)|valid_number/i.test(message)) reason = "needs to be a number";
  else if (/greater than or equal to/i.test(message) && number) reason = `must be at least ${shown}`;
  else if (/less than or equal to/i.test(message) && number) reason = `can be at most ${shown}`;
  else if (/greater than/i.test(message) && number) reason = `must be more than ${shown}`;
  else if (/less than/i.test(message) && number) reason = `must be less than ${shown}`;
  else if (/at least 1 item|too_short/i.test(message)) reason = "needs at least one entry";
  return `${label} ${reason}.`;
}
