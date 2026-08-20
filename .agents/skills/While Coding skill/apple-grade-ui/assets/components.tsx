/**
 * APPLE-GRADE UI — THE REFERENCE IMPLEMENTATION
 *
 * The component catalog in `references/03-components.md` is the specification.
 * This file is the answer. Copy it into the project's component package (the
 * path the profile names) and import from there.
 *
 * WHY THIS FILE EXISTS
 * A specification tells you a button is `h-11 px-4 rounded-md text-callout`.
 * Turning that into correct markup — with the hover guard, the pressed scale,
 * the focus ring, the disabled explanation, the loading width lock, and the
 * right ARIA — is a dozen decisions per component, and every one of them is a
 * chance to drift. Drift is what makes an interface look almost-right.
 * Copying removes the drift. Do not retype these from the spec tables.
 *
 * ASSUMPTIONS
 *   React 18+ · TypeScript · Tailwind (v3 with `assets/tailwind.preset.js`,
 *   or v4 with the tokens exposed via @theme).
 * The token layer in `assets/tokens.css` is framework-neutral. If the project
 * is Vue, Svelte, or plain CSS, port these components — the class strings and
 * the state logic carry over unchanged.
 *
 * RULES THIS FILE ENCODES SO YOU DON'T HAVE TO REMEMBER THEM
 *   Law 1  every value is a token — no raw hex, px, or arbitrary values
 *   Law 3  one filled accent action per screen (`<Button variant="filled">`)
 *   Law 4  every interactive element clears 44×44
 *   Law 6  named properties, spring easing, reduced-motion honored
 *   Law 9  every state exists: hover, pressed, focus, disabled, loading, empty, error
 *
 * All components forward refs and spread the native props of the element they
 * render, so they compose with routers, forms, and analytics without wrappers.
 */

import {
  forwardRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

/* ------------------------------------------------------------------ utility */

/** Join class names, dropping falsy ones. Replace with the project's `cn`/`clsx` if it has one. */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/* ------------------------------------------------------------------- Button */

type ButtonVariant =
  | "filled"
  | "filled-success"
  | "filled-danger"
  | "tinted"
  | "gray"
  | "plain"
  | "outline";

type ButtonSize = "sm" | "md" | "lg" | "xl";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  // `filled` is THE primary action. Law 3: exactly one per screen viewport.
  filled: "bg-accent text-label-on-accent hover:bg-accent-strong",
  "filled-success": "bg-success text-label-on-accent",
  "filled-danger": "bg-danger text-label-on-accent",
  tinted: "bg-accent-tint text-accent-text hover:bg-accent-tint",
  gray: "bg-fill-tertiary text-label hover:bg-fill-secondary",
  plain: "bg-transparent text-accent-text",
  outline: "bg-transparent text-label border border-control",
};

const BUTTON_SIZE: Record<ButtonSize, string> = {
  // `sm` is visually 32px but keeps a 44px hit area via .tap-expand (Law 4).
  sm: "h-8 px-3 text-footnote font-semibold rounded-sm tap-expand",
  md: "h-11 px-4 text-callout font-semibold rounded-md",
  lg: "h-13 px-5 text-headline font-semibold rounded-md",
  xl: "h-14 px-6 text-headline font-bold rounded-lg",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Locks width and swaps the icon for a spinner. The label stays put. */
  loading?: boolean;
  /**
   * Why the button is disabled. Law 9: a disabled primary action with no
   * explanation is a dead end, so this is REQUIRED whenever `disabled` is set.
   * It is rendered adjacent to the button and linked for screen readers.
   */
  disabledReason?: string;
  iconLeading?: ReactNode;
  iconTrailing?: ReactNode;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "tinted",
    size = "md",
    loading = false,
    disabled = false,
    disabledReason,
    iconLeading,
    iconTrailing,
    fullWidth = false,
    className,
    children,
    ...props
  },
  ref,
) {
  const inert = disabled || loading;
  const reasonId = disabledReason ? `${props.id ?? "btn"}-reason` : undefined;

  const button = (
    <button
      ref={ref}
      // A button inside a <form> defaults to submit and will reload the page.
      // Defaulting to "button" makes the safe case the automatic one.
      type={props.type ?? "button"}
      disabled={inert}
      aria-disabled={inert || undefined}
      aria-busy={loading || undefined}
      aria-describedby={cn(props["aria-describedby"] ?? "", reasonId ?? "").trim() || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-2 select-none",
        "transition-[background-color,transform,opacity] duration-instant ease-standard",
        // `hover:` is pointer-only: the preset sets future.hoverOnlyWhenSupported,
        // so these never stick after a tap on touch.
        "active:scale-press",
        "focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2",
        "disabled:opacity-40 disabled:pointer-events-none",
        "motion-reduce:transition-none motion-reduce:active:scale-100",
        BUTTON_SIZE[size],
        BUTTON_VARIANT[variant],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    >
      {loading ? <Spinner className="size-5" /> : iconLeading}
      <span className={cn(loading && "opacity-70")}>{children}</span>
      {!loading && iconTrailing}
    </button>
  );

  if (!disabledReason) return button;

  // The explanation ships WITH the button so it cannot be forgotten downstream.
  return (
    <span className="inline-flex flex-col items-start gap-1">
      {button}
      <span id={reasonId} className="text-footnote text-label-secondary">
        {disabledReason}
      </span>
    </span>
  );
});

/* ------------------------------------------------------------------ Spinner */

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin motion-reduce:animate-none", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" opacity="0.25" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* --------------------------------------------------------------------- Card */

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** `deep` is the one hero card per screen. Never two. */
  tone?: "surface" | "secondary" | "deep";
  padding?: "none" | "sm" | "md";
  interactive?: boolean;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(function Card(
  { tone = "surface", padding = "md", interactive = false, className, ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-xl",
        // Light mode: elevation, not a border. Dark mode: shadows don't read on
        // black, so a hairline supplies the edge instead.
        tone === "surface" && "bg-surface shadow-e1 dark:border dark:border-separator",
        // A nested card must not stack shadows — it changes surface instead.
        tone === "secondary" && "bg-surface-secondary",
        tone === "deep" && "bg-deep text-label-on-accent rounded-2xl",
        padding === "sm" && "p-4",
        padding === "md" && "p-5",
        interactive &&
          "cursor-pointer transition-[transform,box-shadow] duration-instant ease-standard " +
            "active:scale-press-lg hover:shadow-e2 motion-reduce:transition-none",
        className,
      )}
      {...props}
    />
  );
});

/* ------------------------------------------------------------------ ListRow */

export interface ListRowProps {
  leading?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  trailing?: ReactNode;
  /** Renders a chevron. Set ONLY when the row navigates to a new screen. */
  navigates?: boolean;
  onClick?: () => void;
  href?: string;
  density?: "compact" | "default" | "comfortable";
  /** The last row in a group has no separator. */
  last?: boolean;
}

export function ListRow({
  leading,
  title,
  subtitle,
  trailing,
  navigates = false,
  onClick,
  href,
  density = "default",
  last = false,
}: ListRowProps) {
  // ui-allow: div-onclick — naming the banned pattern in the comment that bans it
  // A row that does something is a real element, never a <div onClick>.
  const Tag: "a" | "button" | "div" = href ? "a" : onClick ? "button" : "div";
  const tappable = Tag !== "div";

  return (
    <div className={cn(!last && "border-b border-separator ml-4")}>
      <Tag
        {...(href ? { href } : {})}
        {...(onClick ? { onClick, type: "button" as const } : {})}
        className={cn(
          "w-full flex items-center gap-3 pr-4 -ml-4 pl-4 text-left",
          density === "compact" && "min-h-12 py-2",
          density === "default" && "min-h-14 py-3",
          density === "comfortable" && "min-h-18 py-3",
          tappable &&
            "transition-colors duration-instant hover:bg-fill-quaternary " +
              "active:bg-fill-tertiary focus-visible:outline-2 focus-visible:outline-accent",
        )}
      >
        {leading}
        <span className="flex-1 min-w-0">
          <span className="block text-headline text-label truncate">{title}</span>
          {subtitle && (
            <span className="block text-subhead text-label-secondary line-clamp-2">{subtitle}</span>
          )}
        </span>
        {trailing}
        {navigates && <Chevron className="size-4 text-label-tertiary shrink-0" />}
      </Tag>
    </div>
  );
}

function Chevron({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="m6 3 5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* -------------------------------------------------------------------- Badge */

export type Tone = "success" | "warning" | "danger" | "info" | "accent" | "ai" | "neutral";

const BADGE_TONE: Record<Tone, string> = {
  success: "bg-success-tint text-success-text",
  warning: "bg-warning-tint text-warning-text",
  danger: "bg-danger-tint text-danger-text",
  info: "bg-info-tint text-info-text",
  accent: "bg-accent-tint text-accent-text",
  ai: "bg-ai-tint text-ai-text",
  neutral: "bg-fill-tertiary text-label-secondary",
};

/**
 * A badge STATES A FACT. If it is tappable it is a chip or a button, not a badge.
 * Color is never the only signal — pass a `glyph`, or let the word carry it.
 */
export function Badge({
  tone = "neutral",
  glyph,
  children,
}: {
  tone?: Tone;
  glyph?: ReactNode;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        // text-caption-1 already carries its 500 weight — never restate it.
        "inline-flex items-center gap-1 h-6 px-2.5 rounded-full",
        "text-caption-1 whitespace-nowrap",
        BADGE_TONE[tone],
      )}
    >
      {glyph}
      {children}
    </span>
  );
}

/* -------------------------------------------------------------------- Field */

export interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Always visible. Placeholder-as-label is an accessibility failure. */
  label: string;
  help?: string;
  error?: string;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, help, error, id, className, ...props },
  ref,
) {
  const fieldId = id ?? props.name ?? label.replace(/\s+/g, "-").toLowerCase();
  const helpId = help ? `${fieldId}-help` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;

  return (
    <div className="flex flex-col">
      <label htmlFor={fieldId} className="text-caption-1 text-label-secondary mb-1.5">
        {label}
      </label>
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={cn(helpId ?? "", errorId ?? "").trim() || undefined}
        className={cn(
          "min-h-12 px-3.5 rounded-md bg-fill-tertiary text-body text-label",
          "placeholder:text-label-tertiary",
          "transition-[background-color,box-shadow] duration-instant",
          "focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-0",
          error && "ring-2 ring-danger",
          className,
        )}
        {...props}
      />
      {help && !error && (
        <p id={helpId} className="text-footnote text-label-secondary mt-1.5">
          {help}
        </p>
      )}
      {/* role="alert" so the error is announced the moment it appears. */}
      {error && (
        <p id={errorId} role="alert" className="text-footnote text-danger-text mt-1.5">
          {error}
        </p>
      )}
    </div>
  );
});

/* --------------------------------------------------------------- EmptyState */

/**
 * The three flavors are NOT interchangeable — each implies a different action.
 * An empty area with no explanation is always a bug (Law 9).
 */
export function EmptyState({
  flavor,
  title,
  body,
  action,
  glyph,
}: {
  flavor: "nothing-yet" | "no-results" | "error";
  title: string;
  body: string;
  action?: ReactNode;
  glyph?: ReactNode;
}) {
  return (
    <div
      className="py-16 px-4 text-center max-w-xs mx-auto flex flex-col items-center gap-2"
      role={flavor === "error" ? "alert" : undefined}
    >
      {glyph && <div className="text-label-tertiary mb-2">{glyph}</div>}
      <h3 className="text-title-3 text-label">{title}</h3>
      <p className="text-subhead text-label-secondary">{body}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* ----------------------------------------------------------------- Skeleton */

/**
 * Must match the real content's dimensions, or the page jumps when data lands —
 * which is worse than showing nothing. Content gets skeletons; only
 * indeterminate ACTIONS get spinners.
 */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "bg-fill-quaternary rounded-sm animate-shimmer motion-reduce:animate-none",
        className,
      )}
    />
  );
}

/** Text block skeleton. Last line at 60% width is what makes it read as prose. */
export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-2" aria-busy="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cn("h-3.5", i === lines - 1 ? "w-3/5" : "w-full")} />
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- StatCard */

export function StatCard({
  value,
  label,
  tone = "accent",
  icon,
}: {
  value: ReactNode;
  label: string;
  tone?: Tone;
  icon?: ReactNode;
}) {
  return (
    <Card padding="sm" className="flex flex-col gap-2">
      {icon && (
        <span
          className={cn(
            "inline-flex items-center justify-center size-9 rounded-md",
            BADGE_TONE[tone],
          )}
        >
          {icon}
        </span>
      )}
      {/* text-title-2 already carries 700. `tabular` stops the value jittering
          when it updates in place. */}
      <span className="text-title-2 text-label tabular">{value}</span>
      <span className="text-subhead text-label-secondary">{label}</span>
    </Card>
  );
}
