import { LayoutDashboard, Scale } from "lucide-react";
import { type KeyboardEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { type AppMode, MODE_HOME, MODE_NAME, useAppMode, useModeFailure } from "../../lib/mode";
import { cx } from "../ui";

/** The one place the mode changes: save the setting (the screen shows it at once), then go to that mode's home. */
export function useModeSwitch() {
  const { mode, isShariah, setMode } = useAppMode();
  const navigate = useNavigate();
  const choose = (next: AppMode) => {
    if (next !== mode) void setMode(next);
    void navigate(MODE_HOME[next]);
  };
  return { mode, isShariah, choose, toggle: () => choose(isShariah ? "quant" : "shariah") };
}

// The top bar measures itself (a container), and each piece decides from the bar's own width how much to say. Below
// the widths named here a piece drops its words and becomes an icon, so nothing wraps onto a second line.
const MODE_BUTTON =
  "flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[7px] px-2 text-[13px] font-medium " +
  "transition-all @min-[820px]:gap-2 @min-[820px]:px-3.5";
const MODE_ON_QUANT = "bg-surface text-ink shadow-sm";
const MODE_ON_SHARIAH = "bg-emerald-700 text-white shadow-sm";
const MODE_OFF = "text-ink-3 hover:text-ink";
const ONE_CLICK =
  "ml-1 hidden rounded-full bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 " +
  "@min-[900px]:inline dark:text-emerald-200";

const ORDER: AppMode[] = ["quant", "shariah"];

/** Arrow keys move between the two choices and pick the one they land on, as radio buttons do. */
function arrowTarget(mode: AppMode, key: string): AppMode | null {
  const at = ORDER.indexOf(mode);
  if (key === "ArrowRight" || key === "ArrowDown") return ORDER[(at + 1) % ORDER.length] ?? null;
  if (key === "ArrowLeft" || key === "ArrowUp") return ORDER[(at + ORDER.length - 1) % ORDER.length] ?? null;
  return null;
}

const OPTIONS: Record<AppMode, { icon: typeof Scale; name: string }> = {
  quant: { icon: LayoutDashboard, name: MODE_NAME.quant },
  shariah: { icon: Scale, name: MODE_NAME.shariah },
};

interface RadioProps {
  mode: AppMode;
  current: AppMode;
  choose: (mode: AppMode) => void;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
  setRef: (el: HTMLButtonElement | null) => void;
}

function ModeRadio(props: RadioProps) {
  const { mode, current, choose, onKeyDown, setRef } = props;
  const checked = mode === current;
  const Icon = OPTIONS[mode].icon;
  const on = mode === "shariah" ? MODE_ON_SHARIAH : MODE_ON_QUANT;
  return (
    <button
      ref={setRef}
      type="button"
      role="radio"
      aria-checked={checked}
      tabIndex={checked ? 0 : -1}
      aria-label={OPTIONS[mode].name}
      onClick={() => choose(mode)}
      onKeyDown={onKeyDown}
      className={cx(MODE_BUTTON, checked ? on : MODE_OFF)}
    >
      <Icon className="size-4" aria-hidden />
      {mode === "quant" ? (
        <span>
          <span className="hidden @min-[640px]:inline">Institutional </span>QuantOS
        </span>
      ) : (
        <span>{MODE_NAME.shariah}</span>
      )}
      {mode === "shariah" && !checked && <span className={ONE_CLICK}>1-Click</span>}
    </button>
  );
}

export function ModeSwitch() {
  const { mode, choose } = useModeSwitch();
  const buttons = useRef<Partial<Record<AppMode, HTMLButtonElement | null>>>({});
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const target = arrowTarget(mode, event.key);
    if (!target) return;
    event.preventDefault();
    choose(target);
    buttons.current[target]?.focus();
  };
  const radio = (own: AppMode) => (
    <ModeRadio
      mode={own}
      current={mode}
      choose={choose}
      onKeyDown={onKeyDown}
      setRef={(el) => void (buttons.current[own] = el)}
    />
  );
  return (
    <div
      role="radiogroup"
      aria-label="Application Mode"
      data-mode-switch
      className="flex shrink-0 rounded-[var(--radius-control)] border border-line bg-surface-2 p-0.5"
    >
      {radio("quant")}
      {radio("shariah")}
    </div>
  );
}

/** The phone's one button: shows the mode you are in, and a tap moves to the other. At least 40 px tall to tap. */
export function PhoneModeButton() {
  const { mode, isShariah, toggle } = useModeSwitch();
  const other = MODE_NAME[isShariah ? "quant" : "shariah"];
  const style = isShariah ? "bg-emerald-700 text-white" : "border border-line bg-surface-2 text-ink-2";
  const Icon = isShariah ? Scale : LayoutDashboard;
  return (
    <button
      type="button"
      data-mode-switch
      onClick={toggle}
      aria-label={`${MODE_NAME[mode]} mode. Switch to ${other}`}
      className={cx("flex h-10 items-center gap-1.5 rounded-full px-3 text-[12px] font-medium", style)}
    >
      <Icon className="size-3.5" aria-hidden />
      <span>{isShariah ? "Shariah" : "Quant"}</span>
    </button>
  );
}

const DISMISS = "font-medium text-brand hover:underline";
const ALERT =
  "flex flex-wrap items-center justify-between gap-2 border-b border-down/30 bg-down-soft px-6 py-2 text-[13px] " +
  "text-ink lg:px-10";

/** Says the new mode aloud, and says plainly when a mode change could not be saved. Always in the page, quiet. */
export function ModeNotice() {
  const { mode } = useAppMode();
  const failure = useModeFailure();
  const [dismissed, setDismissed] = useState<number | null>(null);
  const [heard, setHeard] = useState("");
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    setHeard(`Switched to ${MODE_NAME[mode]}.`);
  }, [mode]);
  const show = failure !== null && failure.at !== dismissed;
  return (
    <>
      <p role="status" className="sr-only">
        {heard}
      </p>
      {show && (
        <div role="alert" className={ALERT}>
          <span>
            Could not switch to {MODE_NAME[failure.wanted]}, so QuantOS is still in {MODE_NAME[mode]}. Click the switch
            to try again.
          </span>
          <button type="button" onClick={() => setDismissed(failure.at)} className={DISMISS}>
            Dismiss
          </button>
        </div>
      )}
    </>
  );
}
