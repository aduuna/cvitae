# Design language

The interface should feel like a precise writing tool, in the spirit of the Typst web app: black on white,
thin lines, compact controls, and the document as the only thing with visual weight. Color is reserved
for the CV itself.

## Principles

1. **Monochrome.** The UI uses black, white and grays. The only non-gray colors are `danger` (destructive
   actions and errors) and `placeholder` (highlighted gaps inside CV previews).
2. **The page is the hero.** Chrome is quiet and thin; previews sit on a gray canvas with white pages.
3. **Density with air.** Compact controls (32px default height), 14px base text, generous gaps between
   groups rather than inside them.
4. **One way to do each thing.** Every style comes from tokens; every control comes from a primitive in
   `$lib/components/ui`. Pages compose primitives; they do not restyle them.
5. **Quiet motion.** Short fades and slides only where they explain a change.

## Tokens (single source of truth)

All tokens live in `apps/web/src/app.css`. Tailwind v4 generates utilities from `@theme`. The default
Tailwind palette is removed so non-token colors cannot be used by accident.

```css
@import "tailwindcss";
@import "@fontsource-variable/geist";
@import "@fontsource-variable/geist-mono";

@theme {
  /* Reset defaults: only the colors below exist. */
  --color-*: initial;

  /* Raw scale. Do not use these names in components; use the semantic tokens. */
  --color-white: #ffffff;
  --color-black: #0a0a0a;
  --color-gray-50: #fafafa;
  --color-gray-100: #f4f4f5;
  --color-gray-200: #e4e4e7;
  --color-gray-300: #d4d4d8;
  --color-gray-400: #a1a1aa;
  --color-gray-500: #71717a;
  --color-gray-600: #52525b;
  --color-gray-700: #3f3f46;
  --color-gray-900: #18181b;
  --color-red-700: #b91c1c;
  --color-yellow-200: #ffe58a;

  /* Semantic tokens: the only color names components may use. */
  --color-canvas: var(--color-gray-100);      /* app background behind pages and panels */
  --color-surface: var(--color-white);        /* panels, inputs, menus, pages */
  --color-subtle: var(--color-gray-50);       /* hover rows, secondary panels */
  --color-muted: var(--color-gray-100);       /* pressed, selected backgrounds */
  --color-line: var(--color-gray-200);        /* default borders and dividers */
  --color-line-strong: var(--color-gray-300); /* input borders, splitters */
  --color-fg: var(--color-gray-900);          /* primary text */
  --color-fg-muted: var(--color-gray-500);    /* secondary text, captions (4.8:1 on white) */
  --color-fg-faint: var(--color-gray-400);    /* placeholders in inputs, disabled text */
  --color-accent: var(--color-black);         /* primary buttons, focus rings, active nav */
  --color-accent-fg: var(--color-white);      /* text on accent */
  --color-danger: var(--color-red-700);
  --color-placeholder: var(--color-yellow-200);

  /* Type */
  --font-sans: "Geist Variable", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono Variable", ui-monospace, monospace;

  --text-xs: 12px;   --text-xs--line-height: 16px;
  --text-sm: 13px;   --text-sm--line-height: 18px;
  --text-base: 14px; --text-base--line-height: 20px;
  --text-lg: 16px;   --text-lg--line-height: 24px;
  --text-xl: 20px;   --text-xl--line-height: 28px;
  --text-2xl: 24px;  --text-2xl--line-height: 32px;

  /* Shape */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;

  /* Elevation: used only for menus, dialogs and preview pages */
  --shadow-page: 0 1px 2px rgb(0 0 0 / 0.06), 0 4px 16px rgb(0 0 0 / 0.06);
  --shadow-pop: 0 4px 24px rgb(0 0 0 / 0.12);

  /* Motion */
  --ease-out: cubic-bezier(0.2, 0, 0, 1);
}

@layer base {
  html { font-family: var(--font-sans); font-size: var(--text-base); color: var(--color-fg); background: var(--color-canvas); }
  :focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
  ::selection { background: var(--color-fg); color: var(--color-surface); }
  @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
}
```

Spacing uses Tailwind's default 4px step (`p-1` = 4px, `p-2` = 8px, ...). Use multiples of 4 only.

### Enforcement

A test in `apps/web/tests/tokens.test.ts` (run by `bun run test`) scans `src/lib/components` and
`src/routes` and fails if it finds raw palette names (`gray-`, `black`, `white`, `red-`, `yellow-`),
hex colors or `rgb(` in class lists or style blocks. Only `app.css` may contain them.

### Dark mode

Not in v1. Because components use semantic tokens only, dark mode later means redefining the semantic
tokens under a `[data-theme="dark"]` selector, with no component changes.

## Typography

| Use | Class | Weight |
|---|---|---|
| Page title (one per page) | `text-xl` | 600 |
| Section heading in a page | `text-lg` | 600 |
| Body, inputs, buttons | `text-base` | 400 (buttons 500) |
| Secondary text, table meta | `text-sm text-fg-muted` | 400 |
| Captions, badges, shortcuts | `text-xs` | 500 |
| Code, Typst editor, stacks, file sizes | `font-mono text-sm` | 400 |

No font sizes outside the scale. No italics in the UI (italics belong to CVs). Numbers in tables use
`tabular-nums`.

## Icons

- Library: `@lucide/svelte`, only via `$lib/components/ui/Icon.svelte`.
- Defaults: 16px, stroke width 1.5, `currentColor`. Use 20px only in empty states.
- Icons accompany labels; icon-only buttons need a tooltip and an `aria-label`.
- The logo and third-party marks are images, not icons. The logo is `apps/web/static/logo.svg`
  (also the favicon; PNG sizes beside it), shown through `$lib/components/shell/Logo.svelte`.
  Third-party marks live in `apps/web/static/brand/`. The Google mark on "Continue with Google" keeps
  Google's colours, as Google's sign-in branding requires; it is the only colour in the chrome besides
  `danger` and `placeholder`.

| Purpose | Lucide icon |
|---|---|
| Documents | `FileText` |
| Profiles | `UserRound` |
| Import | `Upload` |
| Tailor | `Target` |
| Templates | `LayoutTemplate` |
| Settings | `Settings` |
| New | `Plus` |
| Duplicate | `Copy` |
| Delete | `Trash2` |
| Download / export | `Download` |
| Versions | `History` |
| Drag handle | `GripVertical` |
| Collapse side nav | `PanelLeftClose` / `PanelLeftOpen` |
| Placeholder warning | `CircleAlert` |
| Plan limit reached | `CircleAlert` |
| Code mode | `Code` |
| Form mode | `ListTree` |

## Layout

```
+------+------------------+------------------------------------------------+
| logo |                  | Top bar (48px): title, actions                 |
|      |  Side nav        +------------------------------------------------+
|      |  240px           |                                                |
|      |  (collapsible    |  Page content                                  |
|      |   to 56px icon   |  max-width 960px for list and form pages,      |
|      |   rail)          |  full width for the editor                     |
|      |                  |                                                |
+------+------------------+------------------------------------------------+
```

- **Side nav:** `bg-surface`, right border `border-line`. Items are 32px tall, icon plus label, radius
  `md`. Active item: `bg-muted text-fg font-medium` with a 2px `accent` bar on the left. Hover:
  `bg-subtle`. Bottom of the nav: plan badge and usage ("3 of 5 AI runs"), then the account menu.
- **Top bar:** `bg-surface`, bottom border `border-line`, 48px, page title left, primary action right.
- **Pages:** `bg-canvas` outside content cards; list and form pages use a centered column (max 960px)
  of `bg-surface` cards with `border-line` and radius `lg`.
- **Editor:** full width, split into edit panel (min 360px) and preview panel, with a draggable splitter
  (`border-line-strong`, 4px hit area). Split ratio persists per user in local storage, wrapped in
  try/catch.
- **Preview canvas:** `bg-canvas`, pages are `bg-surface` with `shadow-page`, 24px gap between pages,
  zoom control (fit width, 75%, 100%, 125%) in the panel header.
- **Breakpoints:** at under 1024px the side nav collapses to the icon rail; at under 768px the editor
  stacks (preview behind a "Preview" toggle) and editing is read-only with download available.

## Components

All primitives live in `apps/web/src/lib/components/ui/`. Each has a Vitest test for its variants and
keyboard behaviour. Variants are implemented with one class map per component (a `variants` object),
not by passing class strings from pages.

| Component | Variants and sizes | Notes |
|---|---|---|
| `Button` | `primary` (accent bg, accent-fg text), `secondary` (surface bg, line-strong border), `ghost` (no border, subtle on hover), `danger` (danger text, danger border on hover). Sizes `sm` 28px, `md` 32px, `lg` 40px. | Optional leading icon. Loading state replaces the icon with a spinner and keeps width. |
| `IconButton` | `ghost`, `secondary`; square 28/32px | Requires `label` prop for aria-label and tooltip. |
| `Input`, `Textarea` | One style; sizes `md` 32px | `bg-surface`, `border-line-strong`, radius `md`, focus ring accent. Error state: danger border and message below. |
| `Select`, `Combobox` | Same as Input | Menu uses `shadow-pop`. |
| `SegmentedControl` | 2 to 4 options | Used for form/Typst mode and similar two-way switches (the AI model is a `Select`: there are more than four). Selected: `bg-surface` with `shadow-page` on a `bg-muted` track. |
| `Checkbox`, `Switch` | One style | Accent when on. |
| `Tabs` | Underline style | Active tab: fg text and 2px accent underline. |
| `Dialog` | `sm` 400px, `md` 560px | Title, body, footer with actions right-aligned; primary action last. Escape closes; focus trapped. |
| `ConfirmDialog` | Built on Dialog | Destructive confirmations use a `danger` primary button and, for account deletion, typed confirmation. |
| `Menu` | Dropdown | Items 32px, shortcuts in `text-xs text-fg-muted` aligned right. |
| `Toast` | `info`, `error` | Bottom right, auto-dismiss after 4s (errors stay until dismissed). |
| `Tooltip` | One style | `bg-fg text-surface text-xs`, 400ms delay. |
| `Badge` | `neutral`, `outline` | `text-xs`, radius `sm`. Used for plan, template name, "Ejected". |
| `Card` | One style | `bg-surface border-line rounded-lg`. |
| `EmptyState` | One style | 20px icon, one-line title, one-line hint, one primary action. |
| `Skeleton` | Lines, block | `bg-muted` with a slow pulse. |
| `Kbd` | One style | `font-mono text-xs border-line rounded-sm`. |
| `Splitter` | Vertical | Keyboard resizable with arrow keys. |
| `Dropzone` | One style | Dashed `border-line-strong`, accepts PDF and DOCX, shows file name and size in mono. |
| `Placeholder` | Inline | Used in form fields to show `[[...]]` gaps: `bg-placeholder` text `fg`, radius `sm`. |

### States

| State | Treatment |
|---|---|
| Hover | `bg-subtle` (ghost, rows), border `fg-muted` (secondary) |
| Active / pressed | `bg-muted` |
| Selected | `bg-muted font-medium` |
| Focus | 2px accent outline, 2px offset, keyboard only (`:focus-visible`) |
| Disabled | 40% opacity, `cursor-not-allowed`, no hover change |
| Loading | Spinner (Lucide `LoaderCircle`, spinning) in place of the leading icon; button text stays |
| Error | `danger` border and a message in `text-sm text-danger` under the field |

### Motion

- Durations: 120ms for hover and press, 180ms for menus and dialogs. Easing `--ease-out`.
- Menus and dialogs fade and move 4px. Nothing bounces. No motion on page navigation.
- Respect `prefers-reduced-motion` (handled globally in `app.css`).

## Page patterns

- **List pages** (Documents, Profiles, Tailor history): top bar with title and a primary "New ..."
  button; a table-like list of rows (48px) with name, meta in `fg-muted`, and a row menu.
  Empty state when there is nothing yet.
- **Form pages** (Profile editor, Settings): stacked cards, each with a heading and fields. Labels above
  fields, `text-sm font-medium`. Help text under fields in `text-sm text-fg-muted`.
- **Generation progress** (Import, Tailor): a card with the current step text, a thin indeterminate
  progress bar (`bg-accent` on `bg-muted`), elapsed seconds in mono, and a cancel button. Announced via
  `aria-live="polite"`.
- **Review screen** (after tailoring): three tabs on narrow screens, three columns on wide screens:
  Preview, Changes, Gaps. Changes show source text in `fg-muted` above the new text in `fg`.

## Copy

- Sentence case for everything, including buttons and headings.
- Plain, specific, calm. Say what happened and what to do next: "Import failed. The PDF is password
  protected. Remove the password and try again."
- Buttons are verbs: "Tailor CV", "Export PDF", "Delete CV". Never "OK" or "Submit".
- No emojis, no exclamation marks, no hype words (magic, supercharge, effortless, AI-powered).
- Name the model plainly where it matters: "Generated with MiMo Flash", "Extracted with Claude Haiku".
  Pro models carry "(Pro)" in model lists.
- Placeholders read as instructions: "[[number of users]]", "[[latency before and after]]".
- Numbers: use digits, thousands separators, and units ("150 AI runs", "10 MB").

## Accessibility

- WCAG 2.2 AA contrast for all text (the token pairs above meet it).
- Everything reachable and operable by keyboard, including reordering (Alt+Up / Alt+Down) and the splitter.
- Visible focus on every interactive element.
- Form fields have labels; errors are linked with `aria-describedby`.
- Preview pages have `role="img"` with an `aria-label` of "Page 1 of 2"; the PDF export is the
  accessible version of the CV.

## The CV templates (inside the preview)

Templates are typeset documents, not UI, so they may use color (for example the navy rules in `classic`).
They must still:

- Render placeholders with the same yellow (`#ffe58a`) used by the UI token.
- Keep body text at 9 to 11pt, margins at least 1.2cm, and single-column body flow.
- Use fonts bundled with the renderer (see `docs/BACKEND.md`).
