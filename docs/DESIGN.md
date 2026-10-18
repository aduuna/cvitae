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
  --color-gray-800: #27272a;
  --color-gray-850: #1f1f23;
  --color-gray-900: #18181b;
  --color-red-400: #f87171;
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
  --color-placeholder-fg: var(--color-gray-900); /* text on placeholder, dark in both themes */
  --color-paper: var(--color-white);          /* CV pages in previews, white in both themes */
  --color-paper-mark: var(--color-gray-900);  /* marks on CV pages, dark in both themes */
  --color-scrim: var(--color-gray-900);       /* dialog backdrop, used at 30% */

  /* Type */
  --font-sans: "Geist Variable", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono Variable", ui-monospace, monospace;

  --text-xs: 12px;   --text-xs--line-height: 16px;
  --text-sm: 13px;   --text-sm--line-height: 18px;
  --text-base: 14px; --text-base--line-height: 20px;
  --text-lg: 16px;   --text-lg--line-height: 24px;
  --text-xl: 20px;   --text-xl--line-height: 28px;
  --text-2xl: 24px;  --text-2xl--line-height: 32px;
  /* Display sizes: the landing page only */
  --text-3xl: 32px;  --text-3xl--line-height: 40px;
  --text-4xl: 48px;  --text-4xl--line-height: 56px;

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

:root[data-theme="dark"] {
  color-scheme: dark;
  --color-canvas: var(--color-black);
  --color-surface: var(--color-gray-900);
  --color-subtle: var(--color-gray-850);
  --color-muted: var(--color-gray-800);
  --color-line: var(--color-gray-800);
  --color-line-strong: var(--color-gray-700);
  --color-fg: var(--color-gray-100);
  --color-fg-muted: var(--color-gray-400);
  --color-fg-faint: var(--color-gray-500);
  --color-accent: var(--color-white);
  --color-accent-fg: var(--color-black);
  --color-danger: var(--color-red-400);
  --color-scrim: var(--color-black);
}

@layer base {
  html { color-scheme: light; font-family: var(--font-sans); font-size: var(--text-base); color: var(--color-fg); background: var(--color-canvas); }
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

The same test resolves the token pairs in both themes and fails if text pairs (`fg`, `fg-muted` and
`danger` on `surface`, `fg` on `canvas` and `muted`, `accent-fg` on `accent`, `placeholder-fg` on
`placeholder`) drop below 4.5:1, or `accent` on `surface` below 3:1. It also fails if the dark block
misses a theme-dependent token.

### Dark mode

Light and dark themes share every semantic name; the dark theme redefines them under
`:root[data-theme="dark"]` (block above). Components do not branch on the theme (the logo is the one
exception, below) and there is no `dark:` variant.

- **Choice:** Settings, Appearance card: a `SegmentedControl` with System, Light and Dark. System
  follows `prefers-color-scheme` and updates live. The choice is per browser, in local storage under
  `vitae.theme` (absent means System), wrapped in try/catch; it is not stored on the server.
- **State:** `$lib/theme.svelte.ts` holds the choice and the resolved theme; the root layout writes the
  resolved theme to `<html data-theme>`.
- **No flash:** `static/theme.js`, loaded as a blocking script in `app.html`, sets `data-theme` before
  first paint. It is a file, not an inline script, so a strict CSP needs no hash for it.
- **The CV stays as printed:** preview pages use `bg-paper` (white in both themes), and `placeholder`
  and `placeholder-fg` do not change, so highlighted gaps match the rendered CV.
- **Logo:** black line art, shown with Tailwind's `invert` filter on the dark theme. The Google mark
  keeps its colours in both themes.
- **Native controls:** `color-scheme` follows the theme so scrollbars, autofill and select menus match.

## Typography

| Use | Class | Weight |
|---|---|---|
| Page title (one per page) | `text-xl` | 600 |
| Section heading in a page | `text-lg` | 600 |
| Body, inputs, buttons | `text-base` | 400 (buttons 500) |
| Secondary text, table meta | `text-sm text-fg-muted` | 400 |
| Captions, badges, shortcuts | `text-xs` | 500 |
| Code, Typst editor, stacks, file sizes | `font-mono text-sm` | 400 |
| Landing page headline (one) | `text-3xl`, `text-4xl` from 1024px, `tracking-tight` | 600 |
| Landing page section heading | `text-2xl`, `text-3xl` from 640px, `tracking-tight` | 600 |

No font sizes outside the scale; the display sizes (`3xl`, `4xl`) appear on the landing page only. No italics in the UI (italics belong to CVs). Numbers in tables use
`tabular-nums`.

## Icons

- Library: `@lucide/svelte`, only via `$lib/components/ui/Icon.svelte`.
- Defaults: 16px, stroke width 1.5, `currentColor`. Use 20px only in empty states.
- Icons accompany labels; icon-only buttons need a tooltip and an `aria-label`.
- The logo, the landing page's line drawings and third-party marks are images, not icons. The logo is `apps/web/static/logo.svg`
  (also the favicon; PNG sizes beside it), shown through `$lib/components/shell/Logo.svelte`.
  Third-party marks live in `apps/web/static/brand/`. The Google mark on "Continue with Google" keeps
  Google's colours, as Google's sign-in branding requires; it is the only colour in the chrome besides
  `danger` and `placeholder`.

| Purpose | Lucide icon |
|---|---|
| Documents | `FileText` |
| Profiles | `UserRound` |
| Import | `Upload` |
| Paste a CV | `ClipboardPaste` |
| Enter manually | `PenLine` |
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
| Edit with AI | `Sparkles` |
| Send | `Send` |
| Undo | `Undo2` |
| Open a docked panel | `ChevronUp` (and `ChevronDown` to close it) |
| Landing: checked against your facts | `ShieldCheck` |
| Landing: typeset with Typst | `Type` |
| Landing: choice of AI model | `Cpu` |

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
  `bg-subtle`. Bottom of the nav: plan badge (no usage; it lives in Settings), then the account menu.
- **Top bar:** `bg-surface`, bottom border `border-line`, 48px, page title left, primary action right.
- **Pages:** `bg-canvas` outside content cards; list and form pages use a centered column (max 960px)
  of `bg-surface` cards with `border-line` and radius `lg`.
- **Editor:** full width, split into edit panel (min 360px) and preview panel, with a draggable splitter
  (`border-line-strong`, 4px hit area). Split ratio persists per user in local storage, wrapped in
  try/catch.
- **Edit with AI panel:** docked at the bottom of the edit panel (not a third column, which would not
  fit beside the preview at 768px), above `border-line`, on `bg-surface`. Closed, it is a pill button
  (`rounded-full`, `accent` fill like a primary button, 32px) with the Sparkles icon and "Edit with AI", and a
  one-line hint beside it, so it is not missed. Open, it is a 40px bar with the icon, the label and a
  chevron, and the conversation (at most 288px, scrolling) sits over the composer: the part and model
  selects side by side, then a 2-row textarea with the primary Send button beside it (Enter sends,
  Shift+Enter is a new line). Requests are right-aligned `bg-muted` bubbles with the part they are
  limited to above them in `text-xs`; replies are plain `fg` text with fact-guard notes and "Edited
  with <model>." plus Undo in `text-sm text-fg-muted`.
  Open or closed is remembered in local storage (`vitae.editor.aiPanel`), wrapped in try/catch.
- **Preview canvas:** `bg-canvas`, pages are `bg-paper` with `shadow-page`, 24px gap between pages,
  zoom control (fit width, 75%, 100%, 125%) in the panel header. Click to edit: the part under the
  pointer gets one box per line in `paper-mark` (5% fill, 30% outline, radius `sm`) and a pointer
  cursor; the field a click opens gets a 2px `accent` ring for 1.2 s.
- **Breakpoints:** at under 1024px the side nav collapses to the icon rail; at under 768px the editor
  stacks (preview behind a "Preview" toggle) and editing is read-only with download available.

## Components

All primitives live in `apps/web/src/lib/components/ui/`. Each has a Vitest test for its variants and
keyboard behaviour. Variants are implemented with one class map per component (a `variants` object),
not by passing class strings from pages.

| Component | Variants and sizes | Notes |
|---|---|---|
| `Button` | `primary` (accent bg, accent-fg text), `secondary` (surface bg, line-strong border), `ghost` (no border, subtle on hover), `danger` (danger text, danger border on hover). Sizes `sm` 28px, `md` 32px, `lg` 40px. | Optional leading icon. Loading state replaces the icon with a spinner and keeps width. |
| `LinkButton` | Same variants and sizes as `Button` | An `<a>` that looks like a Button, for actions that navigate ("Sign in", "Get started"). Shares Button's class maps, which use `not-disabled:` so they apply to links too. |
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
| `Placeholder` | Inline | Used in form fields to show `[[...]]` gaps: `bg-placeholder` text `placeholder-fg`, radius `sm`. |

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

- **List pages** (Documents, Tailor history): top bar with title and a primary "New ..."
  button; a table-like list of rows (48px) with name, meta in `fg-muted`, and a row menu.
  Empty state when there is nothing yet.
- **Tile pages** (Profiles): the same top bar, then a grid of `bg-surface` tiles (radius `lg`,
  `border-line`, `border-line-strong` on hover): 3 columns on wide screens, 2 from 640px, 1 below.
  A tile has an icon (with a status badge such as Default beside it), the name, and meta in
  `fg-muted` at the bottom; the whole tile opens the item and its menu sits top-right.
- **Form pages** (Profile editor, Settings): stacked cards, each with a heading and fields. Labels above
  fields, `text-sm font-medium`. Help text under fields in `text-sm text-fg-muted`.
- **Generation progress** (Import, Tailor): a card with the current step text, a thin indeterminate
  progress bar (`bg-accent` on `bg-muted`), elapsed seconds in mono, and a cancel button. Announced via
  `aria-live="polite"`.
- **Review screen** (after tailoring): the preview, with a 352px "Next steps" column beside it from
  1024px, or two tabs (Preview, Next steps) below that. Next steps are actions first; the change
  details sit in a folded `<details>`, where changes show source text in `fg-muted` above the new
  text in `fg`.
- **Landing page** (`/`, signed out): the one page outside the app shell, in the spirit of typst.app
  and github.com but in this language. A sticky 56px top bar (`bg-surface/90`, `border-line`): logo and
  name left, "How it works" and a secondary "Sign in" right (a primary "Open app" for signed-in
  users, who see the same page; the hero's and closing "Get started" become "Open app" too). The hero is left-aligned, not centred:
  the display headline, one paragraph, a primary "Get started" and a plain "See how it works" link,
  with a line drawing beside it from 768px (below it on phones). No pill badge, background pattern or
  second large button. Then a `bg-canvas` band with a picture of the CV editor, the flow (numbered
  steps joined by a 1px `line` thread with each step's icon in a circle on it; text left, picture
  right from 1024px, stacked below), a three-column principles band, a "Beyond the CV" band (cover
  letters, the Chrome extension, the ATS score: cards with a small line drawing on `bg-canvas`), a
  `bg-canvas` closing band with a second line drawing and a second "Get started", and a footer.
  Content is 1120px wide with 16px gutters (24px from 640px). The line drawings are monochrome
  cartoons in the logo's style (black strokes, white fills, the chameleon), in
  `apps/web/static/illustrations/` and shown through `$lib/components/landing/Cartoon.svelte`, which
  inverts them on the dark theme as the logo does. The pictures of the app are drawn from its
  own primitives and tokens (`$lib/components/landing/`), marked `role="img"` with a description and
  not operable. The CV pages in them are copies of `templates/<id>/preview.png` in
  `apps/web/static/landing/` (the api image builds the SPA from `apps/web` alone); a test fails when
  a copy no longer matches its template's preview.
  The page is prerendered (its `+page.ts`) so search engines read it without running the app; its
  title, description and structured data come from `$lib/site.ts`. The link-preview image
  `static/og.png` (1200 by 630) is a screenshot of `apps/web/scripts/og-image.html`; the command to
  regenerate it is at the top of that file.

## Copy

- Sentence case for everything, including buttons and headings.
- Plain, specific, calm. Say what happened and what to do next: "Import failed. The PDF is password
  protected. Remove the password and try again."
- Buttons are verbs: "Tailor CV", "Export PDF", "Delete CV". Never "OK" or "Submit".
- No emojis, no exclamation marks, no hype words (magic, supercharge, effortless, AI-powered).
- Name the model plainly where it matters: "Generated with MiMo Flash", "Extracted with Claude Haiku".
  Pro models carry "(Pro)" in model lists.
- Placeholders read as instructions: "[[number of users]]", "[[latency before and after]]".
- Numbers: use digits, thousands separators, and units ("100 CVs", "10 MB").
- AI usage is a percentage of the month's allowance ("15%"), never a count of runs.

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
