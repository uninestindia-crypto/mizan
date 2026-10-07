import { Card, CardHeader } from "../ui";

const BODY = "text-[13.5px] leading-relaxed text-ink-2";

export function AcademyTab() {
  return (
    <div className="grid gap-5 md:grid-cols-3">
      <Card>
        <CardHeader title="1. Rationale & Permissibility" subtitle="Foundational Fiqh" />
        <p className={BODY}>
          Shares represent fractional ownership in real commercial assets (Musharakah). Holding equities is
          fundamentally halal, provided the core business and financial ratios adhere to ethical bounds.
        </p>
      </Card>
      <Card>
        <CardHeader title="2. Zero-Interest Demat Guide" subtitle="Broker Setup" />
        <p className={BODY}>
          Step-by-step instructions for opening a cash-only, zero-margin Demat and trading account with Zerodha, Upstox,
          or Groww without signing interest-bearing credit agreements.
        </p>
      </Card>
      <Card>
        <CardHeader title="3. Beating Inflation Halal" subtitle="Wealth Preservation" />
        <p className={BODY}>
          Keeping cash in savings accounts causes wealth erosion due to inflation. Disciplined equity investment
          protects family capital while upholding ethical and spiritual obligations.
        </p>
      </Card>
    </div>
  );
}
