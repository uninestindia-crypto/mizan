import { ArrowLeft, ArrowRight } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate, useNavigationType } from "react-router";
import { cx, Tooltip } from "./ui";

/**
 * Tracks browser session history within React Router using location keys to provide
 * rock-solid, deterministic canGoBack and canGoForward states, plus native keyboard and
 * mouse navigation shortcuts.
 */
export function useHistoryNav() {
  const navigate = useNavigate();
  const location = useLocation();
  const navType = useNavigationType();

  const [historyState, setHistoryState] = useState<{ keys: string[]; currentIndex: number }>(() => ({
    keys: [location.key || "default"],
    currentIndex: 0,
  }));

  useEffect(() => {
    const currentKey = location.key || "default";

    setHistoryState((prev) => {
      const existingIndex = prev.keys.indexOf(currentKey);

      if (navType === "REPLACE") {
        const nextKeys = [...prev.keys];
        nextKeys[prev.currentIndex] = currentKey;
        return { keys: nextKeys, currentIndex: prev.currentIndex };
      }

      if (existingIndex !== -1) {
        // Moved through history stack via Back or Forward
        return { keys: prev.keys, currentIndex: existingIndex };
      }

      // New navigation: truncate forward history and append new key
      const nextKeys = [...prev.keys.slice(0, prev.currentIndex + 1), currentKey];
      return { keys: nextKeys, currentIndex: nextKeys.length - 1 };
    });
  }, [location.key, navType]);

  const canGoBack = historyState.currentIndex > 0;
  const canGoForward = historyState.currentIndex < historyState.keys.length - 1;

  const goBack = useCallback(() => {
    if (canGoBack) {
      navigate(-1);
    }
  }, [canGoBack, navigate]);

  const goForward = useCallback(() => {
    if (canGoForward) {
      navigate(1);
    }
  }, [canGoForward, navigate]);

  // Global desktop keyboard shortcuts: Alt + ArrowLeft (Back), Alt + ArrowRight (Forward)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          goBack();
        } else if (e.key === "ArrowRight") {
          e.preventDefault();
          goForward();
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [goBack, goForward]);

  // Multi-button mouse navigation: button 3 (Back), button 4 (Forward)
  useEffect(() => {
    const onMouseUp = (e: MouseEvent) => {
      if (e.button === 3) {
        e.preventDefault();
        goBack();
      } else if (e.button === 4) {
        e.preventDefault();
        goForward();
      }
    };
    window.addEventListener("mouseup", onMouseUp);
    return () => window.removeEventListener("mouseup", onMouseUp);
  }, [goBack, goForward]);

  return {
    canGoBack,
    canGoForward,
    goBack,
    goForward,
    historyIndex: historyState.currentIndex,
    historyLength: historyState.keys.length,
  };
}

/**
 * Desktop application Forward and Back navigation buttons.
 * Sits in the top header and mobile header to give browser-grade navigation in app mode.
 */
export function HistoryNav({ compact = false }: { compact?: boolean }) {
  const { canGoBack, canGoForward, goBack, goForward } = useHistoryNav();

  const buttonSize = compact ? "size-7" : "size-8";
  const iconSize = compact ? "size-3.5" : "size-4";

  return (
    <div
      role="group"
      aria-label="Navigation history"
      className="flex shrink-0 items-center rounded-[var(--radius-control)] border border-line bg-surface-2 p-0.5 shadow-xs"
    >
      <Tooltip content={canGoBack ? "Back (Alt + ←)" : "Back"}>
        <span className="inline-flex">
          <button
            type="button"
            onClick={goBack}
            disabled={!canGoBack}
            aria-label="Go back"
            className={cx(
              "flex items-center justify-center rounded-[7px] text-ink-2 transition-all",
              "hover:bg-surface hover:text-ink active:scale-95",
              "disabled:cursor-not-allowed disabled:opacity-30 disabled:text-ink-3 disabled:hover:bg-transparent",
              buttonSize,
            )}
          >
            <ArrowLeft className={iconSize} aria-hidden />
          </button>
        </span>
      </Tooltip>
      <Tooltip content={canGoForward ? "Forward (Alt + →)" : "Forward"}>
        <span className="inline-flex">
          <button
            type="button"
            onClick={goForward}
            disabled={!canGoForward}
            aria-label="Go forward"
            className={cx(
              "flex items-center justify-center rounded-[7px] text-ink-2 transition-all",
              "hover:bg-surface hover:text-ink active:scale-95",
              "disabled:cursor-not-allowed disabled:opacity-30 disabled:text-ink-3 disabled:hover:bg-transparent",
              buttonSize,
            )}
          >
            <ArrowRight className={iconSize} aria-hidden />
          </button>
        </span>
      </Tooltip>
    </div>
  );
}
