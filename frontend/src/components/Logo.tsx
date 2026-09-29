export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 256 256" className={className} role="img" aria-label="QuantOS">
      <defs>
        <linearGradient id="quantos-plate" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1B4D8C" />
          <stop offset="1" stopColor="#0A1A33" />
        </linearGradient>
      </defs>
      <rect x="12" y="12" width="232" height="232" rx="56" fill="url(#quantos-plate)" />
      <polyline
        points="56,184 104,132 140,160 190,84"
        fill="none"
        stroke="#4FAEFF"
        strokeWidth="24"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="190" cy="84" r="22" fill="#34D36A" />
    </svg>
  );
}
