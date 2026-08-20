/**
 * APPLE-GRADE UI — TAILWIND PRESET
 *
 * Maps every token in assets/tokens.css to the exact class names this skill's
 * reference files use. Copy both files into your project.
 *
 * Tailwind v3 — tailwind.config.js:
 *   module.exports = {
 *     presets: [require('./tailwind.preset.js')],
 *     content: ['./src/**\/*.{ts,tsx,js,jsx,html}'],
 *     darkMode: ['class', '[data-theme="dark"]'],
 *   };
 *
 * Tailwind v4 — you do not need this file. Use an @theme block in your CSS that
 * points at the same custom properties, e.g.
 *   @theme { --color-surface: var(--surface); --radius-xl: var(--radius-xl); }
 *
 * WHY THIS EXISTS: with the preset installed, `bg-surface`, `text-body`,
 * `shadow-e1`, `rounded-xl`, `duration-base` and `ease-decelerate` all resolve.
 * Without it those classes silently do nothing, which is worse than an error —
 * the page renders unstyled and looks merely "plain" rather than broken.
 */

/** @type {import('tailwindcss').Config} */
module.exports = {
  future: {
    // Compiles `hover:` to `@media (hover: hover)`, so hover styles never stick
    // after a tap on touch devices. Law 9 requires hover to be pointer-only;
    // this makes plain `hover:` correct everywhere instead of asking every
    // author to remember a media query.
    hoverOnlyWhenSupported: true,
  },
  theme: {
    extend: {
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
      },

      // The eleven type steps. Each carries its own line-height, weight and
      // tracking — never layer leading-* or tracking-* on top of one.
      fontSize: {
        display:     ['var(--text-display-size)',     { lineHeight: 'var(--text-display-lh)',     fontWeight: 'var(--text-display-weight)',     letterSpacing: 'var(--text-display-tracking)' }],
        'title-1':   ['var(--text-title-1-size)',     { lineHeight: 'var(--text-title-1-lh)',     fontWeight: 'var(--text-title-1-weight)',     letterSpacing: 'var(--text-title-1-tracking)' }],
        'title-2':   ['var(--text-title-2-size)',     { lineHeight: 'var(--text-title-2-lh)',     fontWeight: 'var(--text-title-2-weight)',     letterSpacing: 'var(--text-title-2-tracking)' }],
        'title-3':   ['var(--text-title-3-size)',     { lineHeight: 'var(--text-title-3-lh)',     fontWeight: 'var(--text-title-3-weight)',     letterSpacing: 'var(--text-title-3-tracking)' }],
        headline:    ['var(--text-headline-size)',    { lineHeight: 'var(--text-headline-lh)',    fontWeight: 'var(--text-headline-weight)',    letterSpacing: 'var(--text-headline-tracking)' }],
        body:        ['var(--text-body-size)',        { lineHeight: 'var(--text-body-lh)',        fontWeight: 'var(--text-body-weight)',        letterSpacing: 'var(--text-body-tracking)' }],
        callout:     ['var(--text-callout-size)',     { lineHeight: 'var(--text-callout-lh)',     fontWeight: 'var(--text-callout-weight)',     letterSpacing: 'var(--text-callout-tracking)' }],
        subhead:     ['var(--text-subhead-size)',     { lineHeight: 'var(--text-subhead-lh)',     fontWeight: 'var(--text-subhead-weight)',     letterSpacing: 'var(--text-subhead-tracking)' }],
        footnote:    ['var(--text-footnote-size)',    { lineHeight: 'var(--text-footnote-lh)',    fontWeight: 'var(--text-footnote-weight)',    letterSpacing: 'var(--text-footnote-tracking)' }],
        'caption-1': ['var(--text-caption-1-size)',   { lineHeight: 'var(--text-caption-1-lh)',   fontWeight: 'var(--text-caption-1-weight)',   letterSpacing: 'var(--text-caption-1-tracking)' }],
        'caption-2': ['var(--text-caption-2-size)',   { lineHeight: 'var(--text-caption-2-lh)',   fontWeight: 'var(--text-caption-2-weight)',   letterSpacing: 'var(--text-caption-2-tracking)' }],
      },

      colors: {
        // Text tiers — use these, never gray-500 / slate-900.
        label: {
          DEFAULT:      'var(--label)',
          secondary:    'var(--label-secondary)',
          tertiary:     'var(--label-tertiary)',
          quaternary:   'var(--label-quaternary)',
          'on-accent':  'var(--label-on-accent)',
        },

        // Surfaces
        canvas:  'var(--canvas)',
        surface: {
          DEFAULT:    'var(--surface)',
          secondary:  'var(--surface-secondary)',
          elevated:   'var(--surface-elevated)',
        },

        // Control backgrounds — translucent, so one token works everywhere.
        fill: {
          DEFAULT:    'var(--fill)',
          secondary:  'var(--fill-secondary)',
          tertiary:   'var(--fill-tertiary)',
          quaternary: 'var(--fill-quaternary)',
        },

        separator: {
          DEFAULT: 'var(--separator)',
          opaque:  'var(--separator-opaque)',
        },

        // Brand + semantic tones. `-text` variants are the contrast-safe
        // version for small text; the base token is for fills and glyphs.
        accent: {
          DEFAULT: 'var(--accent)',
          strong:  'var(--accent-strong)',
          // The accent split. `accent` is the FILL (bg-accent + text-label-on-accent);
          // `accent-text` is the same identity used as WORDS on a surface. In dark
          // mode no single value can do both, so text-accent-text is not optional
          // sugar — it is the token that keeps accent-colored text legible.
          text:    'var(--accent-text)',
          tint:    'var(--accent-tint)',
        },
        deep:    'var(--deep)',
        success: { DEFAULT: 'var(--success)', text: 'var(--success-text)', tint: 'var(--success-tint)' },
        warning: { DEFAULT: 'var(--warning)', text: 'var(--warning-text)', tint: 'var(--warning-tint)' },
        danger:  { DEFAULT: 'var(--danger)',  text: 'var(--danger-text)',  tint: 'var(--danger-tint)'  },
        info:    { DEFAULT: 'var(--info)',    text: 'var(--info-text)',    tint: 'var(--info-tint)'    },
        ai:      { DEFAULT: 'var(--ai)',      text: 'var(--ai-text)',      tint: 'var(--ai-tint)'      },
      },

      // `border-separator` is the decorative hairline BETWEEN rows and comes from
      // colors. `border-control` is the boundary OF a control and must hold 3:1 —
      // it is a different job with a different contrast floor, so it is a
      // different token. Mixing them up is the most common color mistake here.
      borderColor: {
        control: 'var(--border-control)',
      },

      borderRadius: {
        xs:    'var(--radius-xs)',
        sm:    'var(--radius-sm)',
        md:    'var(--radius-md)',
        lg:    'var(--radius-lg)',
        xl:    'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
        '3xl': 'var(--radius-3xl)',
        full:  'var(--radius-full)',
      },

      // ui-allow: default-shadow — naming the banned classes in the comment that bans them
      // Elevation. Never shadow-md / shadow-lg / shadow-xl — those are
      // Tailwind's defaults and they read as Material Design, not iOS.
      boxShadow: {
        e0: 'var(--shadow-e0)',
        e1: 'var(--shadow-e1)',
        e2: 'var(--shadow-e2)',
        e3: 'var(--shadow-e3)',
        e4: 'var(--shadow-e4)',
      },

      // 4pt grid. Tailwind's default scale is already 4pt-based; these are the
      // additions the reference files name.
      spacing: {
        'safe-b': 'env(safe-area-inset-bottom)',
        'safe-t': 'env(safe-area-inset-top)',
        // Control heights the component specs call for that Tailwind's default
        // scale skips. Still on the 4pt grid.
        13: '3.25rem', // 52 — lg button
        18: '4.5rem',  // 72 — comfortable list row
      },

      // The pressed state. The spec is scale(0.97); without a named token every
      // author reaches for an arbitrary value and they drift apart.
      scale: {
        press: '0.97',      // buttons and small controls
        'press-lg': '0.98', // cards and large surfaces — same feel at larger area
      },

      maxWidth: {
        prose:     'var(--measure-prose)',
        field:     'var(--measure-field)',
        container: 'var(--container-max)',
      },

      minHeight: { tap: 'var(--tap-min)' },
      minWidth:  { tap: 'var(--tap-min)' },

      transitionDuration: {
        instant:    'var(--duration-instant)',
        fast:       'var(--duration-fast)',
        base:       'var(--duration-base)',
        slow:       'var(--duration-slow)',
        deliberate: 'var(--duration-deliberate)',
      },

      transitionTimingFunction: {
        standard:   'var(--ease-standard)',
        decelerate: 'var(--ease-decelerate)',
        accelerate: 'var(--ease-accelerate)',
        spring:     'var(--ease-spring)',
        emphasis:   'var(--ease-emphasis)',
      },

      zIndex: {
        content: 'var(--z-content)',
        sticky:  'var(--z-sticky)',
        chrome:  'var(--z-chrome)',
        overlay: 'var(--z-overlay)',
        modal:   'var(--z-modal)',
        toast:   'var(--z-toast)',
      },

      keyframes: {
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        shimmer: 'shimmer 1.5s linear infinite',
      },
    },
  },
};
