"""The two pages the window shows before and instead of the app: a loading screen, and a plain failure page.

Both are one self-contained piece of HTML with no scripts and nothing fetched, so they paint the instant the window
exists, on any machine, while the engine behind the window is still starting. Their colours are the window's own
first-paint colours, so a dark system never flashes white.
"""

from __future__ import annotations

from html import escape

LIGHT = {"bg": "#f4f6fa", "ink": "#101828", "sub": "#475467", "track": "#e4e7ec", "bar": "#2557d6"}
DARK = {"bg": "#080d17", "ink": "#f2f4f7", "sub": "#98a2b3", "track": "#1d2939", "bar": "#6e9bff"}

# The slow-start line appears by itself after this many seconds; no script is needed.
SLOW_START_AFTER_SECONDS = 8

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>QuantOS</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html, body {{ height: 100%; margin: 0; background: {bg}; color: {ink};
    font: 15px/1.5 "Segoe UI Variable", "Segoe UI", system-ui, sans-serif; }}
  main {{ min-height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 14px; text-align: center; padding: 24px; box-sizing: border-box; }}
  .mark {{ width: 64px; height: 64px; border-radius: 16px; background: linear-gradient(145deg, #12294f, #1c4fa8);
    display: grid; place-items: center; box-shadow: 0 8px 28px rgba(18, 41, 79, .35); }}
  h1 {{ margin: 6px 0 0; font-size: 26px; font-weight: 650; letter-spacing: -.01em; }}
  .tag {{ margin: 0; color: {sub}; }}
  .track {{ width: 220px; height: 4px; border-radius: 4px; background: {track}; overflow: hidden; margin-top: 10px; }}
  .bar {{ width: 40%; height: 100%; border-radius: 4px; background: {bar};
    animation: slide 1.3s ease-in-out infinite; }}
  .status {{ margin: 0; color: {sub}; font-size: 13.5px; }}
  .slow {{ margin: 0; color: {sub}; font-size: 13px; opacity: 0; animation: appear .6s ease {slow}s forwards; }}
  .version {{ position: fixed; bottom: 14px; left: 0; right: 0; text-align: center; color: {sub}; font-size: 12px; }}
  @keyframes slide {{ 0% {{ transform: translateX(-110%); }} 100% {{ transform: translateX(260%); }} }}
  @keyframes appear {{ to {{ opacity: 1; }} }}
  @media (prefers-reduced-motion: reduce) {{
    .bar {{ animation: none; width: 100%; opacity: .55; }}
  }}
</style></head>
<body><main role="status" aria-live="polite">
  <div class="mark" aria-hidden="true">
    <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2"
      stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/>
      <polyline points="15 7 21 7 21 13"/></svg>
  </div>
  <h1>QuantOS</h1>
  <p class="tag">Test before you trade</p>
  <div class="track" aria-hidden="true"><div class="bar"></div></div>
  <p class="status">Starting up&hellip;</p>
  <p class="slow">Still starting. The first start after installing can take a little longer.</p>
</main>
<div class="version">Version {version}</div>
</body></html>
"""

_FAILURE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>QuantOS</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  html, body {{ height: 100%; margin: 0; background: {bg}; color: {ink};
    font: 15px/1.55 "Segoe UI Variable", "Segoe UI", system-ui, sans-serif; }}
  main {{ min-height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 10px; text-align: center; padding: 24px; box-sizing: border-box; max-width: 460px; margin: 0 auto; }}
  h1 {{ margin: 0; font-size: 22px; font-weight: 650; }}
  p {{ margin: 0; color: {sub}; }}
</style></head>
<body><main role="alert">
  <h1>QuantOS could not start</h1>
  <p>Close this window and open QuantOS again.</p>
  <p>If it keeps happening, restart your computer, then open QuantOS once more. Your saved data is safe.</p>
</main></body></html>
"""


def splash_html(*, dark: bool, version: str) -> str:
    """The loading screen. ``version`` is shown as text only: it is escaped, never treated as markup."""
    colours = DARK if dark else LIGHT
    return _PAGE.format(
        **colours, slow=SLOW_START_AFTER_SECONDS, version=escape(version, quote=True)
    )


def failure_html(*, dark: bool) -> str:
    """The page shown instead of the app when the engine could not start, in plain words."""
    return _FAILURE.format(**(DARK if dark else LIGHT))
