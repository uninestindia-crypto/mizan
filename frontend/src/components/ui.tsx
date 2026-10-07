import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { clsx } from "clsx";
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from "lucide-react";
import type { AriaAttributes, ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";
import { createContext, forwardRef, useContext, useId, useRef } from "react";
import { type Tone, tone as toneOf } from "../lib/format";

export { clsx as cx };

// ------------------------------------------------------------------------------ buttons

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: ReactNode;
}

const buttonVariants: Record<ButtonVariant, string> = {
  primary: "bg-brand text-on-brand hover:bg-brand-strong shadow-sm",
  secondary: "bg-surface text-ink border border-line hover:bg-surface-2 hover:border-line-strong",
  ghost: "text-ink-2 hover:text-ink hover:bg-surface-2",
  // White on the light theme's red; the dark theme's red is a light pink, where white is only 2.7 to 1, so dark text.
  danger: "bg-down text-white hover:opacity-90 dark:text-on-brand",
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-[15px] gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, icon, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={clsx(
        "inline-flex items-center justify-center rounded-[var(--radius-control)] font-medium transition-colors",
        "disabled:opacity-50 disabled:cursor-not-allowed select-none whitespace-nowrap",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

// -------------------------------------------------------------------------------- cards

export function Card({
  children,
  className,
  padded = true,
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
  as?: "section" | "div" | "article";
}) {
  return (
    <Tag className={clsx("rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-card)]", padded && "p-5", className)}>
      {children}
    </Tag>
  );
}

export function CardHeader({ title, subtitle, action, className }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={clsx("mb-4 flex items-start justify-between gap-4", className)}>
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-[13px] text-ink-3">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-3">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

// ------------------------------------------------------------------------------- badges

type BadgeTone = "neutral" | "brand" | "up" | "down" | "warn" | "violet";

const badgeTones: Record<BadgeTone, string> = {
  neutral: "bg-surface-2 text-ink-2 border-line",
  brand: "bg-brand-soft text-brand border-transparent",
  up: "bg-up-soft text-up border-transparent",
  down: "bg-down-soft text-down border-transparent",
  warn: "bg-warn-soft text-warn border-transparent",
  violet: "bg-surface-2 text-violet border-transparent",
};

export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: BadgeTone; className?: string }) {
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11.5px] font-medium leading-5", badgeTones[tone], className)}>
      {children}
    </span>
  );
}

// ------------------------------------------------------------------------ numbers/deltas

const toneText: Record<Tone, string> = { up: "text-up", down: "text-down", flat: "text-ink-2" };

export function Delta({ value, children, className, strong = false }: { value: number | null | undefined; children: ReactNode; className?: string; strong?: boolean }) {
  return <span className={clsx("num", toneText[toneOf(value)], strong && "font-semibold", className)}>{children}</span>;
}

export function Stat({ label, value, sub, tone, hint }: { label: ReactNode; value: ReactNode; sub?: ReactNode; tone?: Tone; hint?: string }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1 text-[12.5px] text-ink-3">
        {label}
        {hint && <HelpTip text={hint} />}
      </div>
      <div className={clsx("num mt-1 break-words text-xl font-semibold tracking-tight", tone ? toneText[tone] : "text-ink")}>{value}</div>
      {sub && <div className="num mt-0.5 text-[12.5px] text-ink-3">{sub}</div>}
    </div>
  );
}

// --------------------------------------------------------------------------- form fields

interface FieldInfo {
  htmlFor?: string;
  /** The id of the line under the control (its problem, else its hint). Undefined when there is none. */
  messageId?: string;
  invalid: boolean;
}

const FieldContext = createContext<FieldInfo | null>(null);

type ControlAria = Pick<AriaAttributes, "aria-describedby" | "aria-invalid">;

/**
 * What a control inside a Field carries so a screen reader reads the line under it: the line's id, and "invalid" when
 * that line is a problem. Only the control the label points at (its id is the Field's `htmlFor`) is tied, and anything
 * the control already says for itself is kept.
 */
export function useFieldAria(own: ControlAria & { id?: string }): ControlAria {
  const field = useContext(FieldContext);
  const tied = field !== null && own.id !== undefined && own.id === field.htmlFor ? field : null;
  const ids = [own["aria-describedby"], tied?.messageId].filter(Boolean).join(" ");
  return { "aria-describedby": ids || undefined, "aria-invalid": own["aria-invalid"] ?? (tied?.invalid ? true : undefined) };
}

interface FieldProps {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
}

export function Field({ label, hint, error, children, htmlFor }: FieldProps) {
  const messageId = useId();
  const message = error || hint;
  const info = { htmlFor, messageId: message ? messageId : undefined, invalid: Boolean(error) };
  return (
    <FieldContext.Provider value={info}>
      <div className="flex min-w-0 flex-col gap-1.5">
        <label htmlFor={htmlFor} className="text-[13px] font-medium text-ink-2">
          {label}
        </label>
        {children}
        {message ? (
          <p id={messageId} className={error ? "text-[12.5px] text-down" : "text-[12.5px] text-ink-3"}>
            {message}
          </p>
        ) : null}
      </div>
    </FieldContext.Provider>
  );
}

const controlClass =
  "h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink placeholder:text-ink-3 transition-colors hover:border-line-strong focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/15 disabled:opacity-60";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { prefix?: string; suffix?: string }>(function Input(
  { className, prefix, suffix, ...rest },
  ref,
) {
  const aria = useFieldAria(rest);
  if (!prefix && !suffix) return <input ref={ref} className={clsx(controlClass, className)} {...rest} {...aria} />;
  return (
    <div className="relative">
      {prefix && <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm text-ink-3">{prefix}</span>}
      <input ref={ref} className={clsx(controlClass, "num", prefix && "pl-7", suffix && "pr-9", className)} {...rest} {...aria} />
      {suffix && <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-ink-3">{suffix}</span>}
    </div>
  );
});

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  const aria = useFieldAria(rest);
  return (
    <select className={clsx(controlClass, "appearance-none bg-[length:16px] bg-[right_10px_center] bg-no-repeat pr-9", className)} style={{ backgroundImage: "var(--q-select-arrow)" }} {...rest} {...aria}>
      {children}
    </select>
  );
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  size = "md",
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: { value: T; label: ReactNode }[];
  size?: "sm" | "md";
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-[var(--radius-control)] border border-line bg-surface-2 p-0.5">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={clsx(
              "rounded-[8px] font-medium transition-colors",
              size === "sm" ? "px-2.5 py-1 text-[12.5px]" : "px-3.5 py-1.5 text-[13px]",
              active ? "bg-surface text-ink shadow-sm" : "text-ink-3 hover:text-ink",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

export function Switch({ checked, onChange, label, id }: { checked: boolean; onChange: (value: boolean) => void; label: string; id?: string }) {
  const generated = useId();
  const switchId = id ?? generated;
  return (
    <label htmlFor={switchId} className="inline-flex cursor-pointer items-center gap-2.5 text-sm text-ink-2">
      <button
        id={switchId}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={clsx("relative h-5 w-9 shrink-0 rounded-full transition-colors", checked ? "bg-brand" : "bg-surface-3")}
      >
        <span className={clsx("absolute left-0 top-0.5 size-4 rounded-full bg-white shadow transition-transform", checked ? "translate-x-[18px]" : "translate-x-[2px]")} />
      </button>
      {label}
    </label>
  );
}

// ------------------------------------------------------------------------------ callouts

type CalloutTone = "info" | "warn" | "danger" | "success";

const calloutStyles: Record<CalloutTone, { box: string; icon: ReactNode }> = {
  info: { box: "bg-brand-soft/60 border-brand/20 text-ink", icon: <Info className="size-4 text-brand" aria-hidden /> },
  warn: { box: "bg-warn-soft border-warn/25 text-ink", icon: <AlertTriangle className="size-4 text-warn" aria-hidden /> },
  danger: { box: "bg-down-soft border-down/25 text-ink", icon: <XCircle className="size-4 text-down" aria-hidden /> },
  success: { box: "bg-up-soft border-up/25 text-ink", icon: <CheckCircle2 className="size-4 text-up" aria-hidden /> },
};

export function Callout({ tone = "info", title, children, action, className }: { tone?: CalloutTone; title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  const style = calloutStyles[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={clsx("flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border px-4 py-3 text-[13.5px]", style.box, className)}>
      <div className="flex min-w-[14rem] flex-1 gap-3 self-start">
        <div className="mt-0.5 shrink-0">{style.icon}</div>
        <div className="min-w-0 flex-1">
          {title && <div className="font-semibold">{title}</div>}
          {children && <div className={clsx("text-ink-2", title && "mt-0.5")}>{children}</div>}
        </div>
      </div>
      {action && <div className="shrink-0 pl-7">{action}</div>}
    </div>
  );
}

export function EmptyState({ title, body, action, art, className }: { title: ReactNode; body?: ReactNode; action?: ReactNode; art?: ReactNode; className?: string }) {
  return (
    <div className={clsx("flex flex-col items-center justify-center px-6 py-10 text-center", className)}>
      {art && <div className="mb-4">{art}</div>}
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {body && <p className="mt-1.5 max-w-md text-sm text-ink-2">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("relative overflow-hidden rounded-md bg-surface-2", className)} aria-hidden />;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-3" role="status">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label ?? "Loading"}
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number; label: string }) {
  const clamped = Math.max(0, Math.min(1, value));
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(clamped * 100)} className="h-2 w-full overflow-hidden rounded-full bg-surface-3">
      <div className="h-full rounded-full bg-brand transition-[width] duration-300" style={{ width: `${clamped * 100}%` }} />
    </div>
  );
}

// -------------------------------------------------------------------------- tooltip/help

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <TooltipPrimitive.Root delayDuration={150}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className="z-50 max-w-xs rounded-lg bg-ink px-2.5 py-1.5 text-[12.5px] leading-snug text-surface shadow-[var(--shadow-pop)]"
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-ink" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

export function HelpTip({ text }: { text: string }) {
  return (
    <Tooltip content={text}>
      <button type="button" aria-label={text} className="inline-flex size-4 items-center justify-center rounded-full text-ink-3 hover:text-ink">
        <Info className="size-3.5" aria-hidden />
      </button>
    </Tooltip>
  );
}

// -------------------------------------------------------------------------------- dialog

/**
 * A window opened by state has no Radix trigger, so Radix has nothing to give focus back to and focus fell to the page.
 * Remember the control the person was on when the window opened, and hand focus back to it when it closes.
 */
function useReturnFocus(fallback?: () => HTMLElement | null) {
  const openedFrom = useRef<Element | null>(null);
  const remember = () => {
    openedFrom.current = document.activeElement;
  };
  const giveBack = (event: Event) => {
    event.preventDefault();
    const was = openedFrom.current;
    openedFrom.current = null;
    const stillThere = was instanceof HTMLElement && was.isConnected && was !== document.body;
    (stillThere ? was : fallback?.())?.focus();
  };
  return { remember, giveBack };
}

function DialogHeading({ title, description }: { title: ReactNode; description?: ReactNode }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <DialogPrimitive.Title className="text-lg font-semibold text-ink">{title}</DialogPrimitive.Title>
        {description ? (
          <DialogPrimitive.Description className="mt-1 text-sm text-ink-2">{description}</DialogPrimitive.Description>
        ) : (
          <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
        )}
      </div>
      <DialogPrimitive.Close className="rounded-lg p-1 text-ink-3 hover:bg-surface-2 hover:text-ink" aria-label="Close">
        <X className="size-5" aria-hidden />
      </DialogPrimitive.Close>
    </div>
  );
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  wide = false,
  fallbackFocus,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  /** Where focus goes when the control that opened this window no longer exists (for example, a deleted card). */
  fallbackFocus?: () => HTMLElement | null;
}) {
  const focus = useReturnFocus(fallbackFocus);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px]" />
        <DialogPrimitive.Content
          onOpenAutoFocus={focus.remember}
          onCloseAutoFocus={focus.giveBack}
          className={clsx(
            "q-fade-in fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-line bg-surface p-6 shadow-[var(--shadow-pop)]",
            wide ? "max-w-2xl" : "max-w-md",
          )}
        >
          <DialogHeading title={title} description={description} />
          {children}
          {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export function TooltipProvider({ children }: { children: ReactNode }) {
  return <TooltipPrimitive.Provider>{children}</TooltipPrimitive.Provider>;
}
