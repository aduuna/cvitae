# Product spec

## One-line pitch

Paste a job description, get a CV tailored to it, typeset properly, without the AI inventing anything.

## Who it is for

Job seekers, mostly engineers and other technical professionals, who apply to many roles and want a
different CV for each. They care about typography, one-page discipline and honesty. Many are in Africa
and Europe, which is why payments go through Paystack.

## Core principles

1. **Your facts, better told.** The AI may select, reorder and reword what the user already said. It never
   adds employers, titles, dates, tools, numbers or achievements. Where a stronger bullet needs a number
   the user has not given, the CV shows a highlighted placeholder for the user to fill in.
2. **Structured data first, Typst second.** A user's career lives in a structured profile. CVs are views of
   that profile rendered through templates. Raw Typst editing is an advanced option, not the default.
3. **Fast and quiet.** Black and white UI, no clutter, live preview, keyboard friendly.

## Glossary

| Term | Meaning |
|---|---|
| Profile | A user's master career data: contact details, roles, clients, bullets, skills, education, projects, certifications. A user can have several (for example "Data engineering" and "Backend"). |
| CV (document) | A renderable CV: a profile snapshot (possibly tailored), a template and a name. A user can have many. |
| Job | A saved job description with its title, company, URL and AI analysis. |
| Template | A Typst design that renders any CV. Five ship in v1. |
| Placeholder | Highlighted text in a CV that the user must replace, for example "[[number of users]]". |
| Tailoring | Creating a CV from a profile plus a job, using AI under the no-new-facts rule. |
| AI edit | A change to one CV asked for in words in the editor's "Edit with AI" panel, under the same rule. |
| Ejected CV | A CV whose Typst source and data file the user edits directly. AI tailoring no longer applies to it. |
| AI model | What runs an AI task: MiMo Flash, Claude Haiku or Gemini Flash-Lite on every plan; MiMo Pro, Gemini Flash or Claude Sonnet on Pro. |

## Navigation

A persistent left side nav with one item per feature. Each item is its own route with its own page.
Icons are Lucide, listed in `docs/DESIGN.md`.

| Order | Item | Route | Purpose |
|---|---|---|---|
| 1 | Documents | `/app/documents` | All CVs. Open, create, duplicate, rename, delete. Default landing page. |
| 2 | Profiles | `/app/profiles` | Enter and edit work experience and other career data. New profiles start at `/app/profiles/new`: import a CV (the default) or start from scratch. |
| 3 | Tailor | `/app/tailor` | Paste a job description and generate a tailored CV. Lists saved jobs. |
| 4 | Templates | `/app/templates` | Browse the 5 templates with previews; set a default. |
| 5 | Extension | `/app/extension` | The browser extension: what it does, where to get it, connect this browser, connected browsers. |
| 6 | Settings | `/app/settings` | Account, AI model, billing, data export and deletion. |

The editor for a single CV lives at `/app/documents/[id]` and keeps the side nav visible (collapsible).
A signed-out user sent to the sign-in page from an app page returns to that page after signing in.
The privacy policy is a public page, `/privacy`, linked from the landing page's footer, the sign-in
page, the Extension page and the extension.

## Features and acceptance criteria

### 1. Authentication

- Sign in with Google, or with an email link (passwordless). Firebase Auth.
- `/login?password`, linked from nowhere, has an email and password form in place of the email
  link, for the store review account (`cvitae-review`, made by `apps/api/scripts/review_account.py`).
  There is no sign-up with a password.
- First sign-in creates the user record.
- Signed-out users see a landing page at `/` that shows what the app does before asking them to sign
  in: a hero with a line drawing of the chameleon tailoring a CV, a picture of the CV editor, then the
  flow in five steps (import a CV, keep a profile per direction, tailor to a job, edit the CV, export
  the PDF), each with a picture of that step in the app, then cover letters in the user's tone, the
  Chrome extension that fills in application forms, and the ATS score. "Sign in" sits in the top
  bar; "Get started" sits in the hero and at the bottom. Both open the sign-in page at `/login`.
  Signed-in users see the same page with "Open app" in their place, and the logo in the side nav
  links back to it.
- The landing page is the one public, indexed page: prerendered to static HTML with its title,
  description, canonical URL, link-preview image and schema.org data naming the site "Chameleon
  vitae" with alternate names "cvitae" and "Chameleon CV" (`apps/web/src/lib/site.ts`).
  `robots.txt` keeps crawlers out of `/app/`, `/auth/` and `/api/`; `sitemap.xml` lists `/`.
- All `/app/*` routes require auth; signed-out visitors to them go to `/`.

Done when: a new user can sign in with either method, lands on an empty Documents page with an onboarding
prompt, and signing out returns to `/`.

### 2. Profiles (work experience entry)

- A profile has: basics (name, headline, email, phone, location, links), summary, and ordered sections:
  experience, projects, education, skills, certifications, and custom sections.
- Experience entries have organisation, role, location, start and end dates (end empty means present),
  a tech stack list, bullets, and optional nested engagements (clients or contingent-worker placements),
  each with its own label, location, dates and bullets. This mirrors agency and consulting careers.
- Bullets support **bold** for key figures. Bullets and entries can be reordered by drag and by keyboard.
- Autosave with a visible "Saved" state; no save button.
- A user can have several profiles; one is marked default.

Done when: a user can build a complete profile by hand, reorder anything, reload and see it unchanged,
and create a second profile from scratch or by duplicating the first.

### 3. Import

- Import is how a new profile starts by default. Every "New profile" button opens
  `/app/profiles/new`: one row of tabs with the three ways to start, as alternatives rather than
  steps: "Upload a CV" (selected), "Paste a CV" and "Enter manually" (an empty profile in the
  editor). The AI model picker sits next to Import CV, with a line saying the user checks
  everything before it is saved. Under "Upload a CV", "Or import an earlier upload" lists the 3
  newest distinct files (a file uploaded twice shows once) and "Show all" lists every upload.
- Inputs: PDF or DOCX up to 10 MB, or pasted text.
- The selected AI model extracts a structured profile.
- The model also suggests the profile's name: the kind of work the CV is for, such as "Data
  engineering", never the person's name. Without a suggestion the CV's headline is used. The user
  can change it before saving.
- The user reviews the result in the profile editor before it is saved, with a banner:
  "Imported from <filename>. Check every entry before using it."
- The draft exists only until it is saved, and it cost AI usage, so leaving the review asks first:
  "Save the imported profile?" with Keep reviewing, Discard and Save profile (which then goes on to
  where the user was heading). Closing or reloading the tab gets the browser's own prompt.
- Extraction must not invent content; empty fields stay empty.
- The original file is stored so the user can re-run import later, and can be deleted.

Done when: importing the sample PDF in `templates/fixtures/` produces a profile whose roles, dates and
bullets match the source, and the user can accept or discard it.

### 4. Tailor

- Form: job description (required, pasted text), job title, company, URL (optional), base profile,
  template, AI model (a select, defaulting to the user's setting).
- Jobs are saved and listed on the Tailor page so the user can tailor again or see what was sent.
  `/app/tailor?job=<id>` opens with that saved job chosen; the browser extension links there after
  saving a job ad.
- Generation produces a new CV and opens a review screen: the **Preview** of the tailored CV, with
  **Next steps** beside it, kept short and actionable:
  1. **Fill in N gaps**: placeholders are highlighted in the preview, so they are counted, not listed;
     "Fill in the editor" opens the CV.
  2. **Not in your profile**: job keywords the profile does not cover (10 shown, "Show all" for the
     rest), "Add the ones that are true to your profile, then tailor again", and "Edit profile".
  3. **What changed**: one folded line ("4 reworded, 2 kept as written, 8 left out, 1 corrected by the
     fact check") that opens the details: each bullet with its source, left-out bullets and every
     fact-check correction.
- The fact guard flags any rewritten bullet that contains a number not present in its source; flagged
  numbers are turned into placeholders automatically.
- The user can accept (opens the editor), regenerate with another model, or discard.
- Generation shows progress text ("Reading the job description", "Selecting your strongest experience",
  "Writing the CV") and can take up to about a minute.

Done when: tailoring the fixture profile against the fixture job description yields a one-page CV in the
chosen template, every bullet traces to a source bullet, no unflagged new numbers exist, and switching
the model and regenerating works.

### 5. Documents and the editor

- Documents list: name, template, linked job (if any), last edited, page count. Actions: open, duplicate,
  rename, delete (with confirmation), download PDF.
- Users can have multiple CVs; limits depend on plan (see Plans).
- Editor layout: left panel edits, right panel shows the live preview (pages rendered as SVG on a gray
  canvas, like typst.app). Top bar: document name, template picker, page count, export button.
- Left panel has two modes:
  - **Form** (default): the same section editor as Profiles, scoped to this CV. Changes here do not
    change the profile.
  - **Typst** (after eject): a two-file code editor for `main.typ` and `data.json` with Typst
    diagnostics shown inline. Ejecting asks for confirmation and explains that AI tailoring and template
    switching stop applying to this CV. Ejecting is one-way; the user can duplicate the CV first.
- Preview updates within about one second of the user stopping typing. On a compile error the last good
  preview stays visible with an error panel listing line and message.
- Click to edit: hovering the preview marks the part under the pointer, and a click opens the form
  field it comes from (a bullet, a role or other item, a section heading, the summary or the header),
  scrolled into view, focused and briefly ringed. Exported PDFs carry no such links. Form-mode CVs
  only; a CV edited as Typst has no form to open.
- Edit with AI: a collapsible panel docked at the bottom of the edit panel (form-mode CVs on wide
  screens; it remembers being open or closed in this browser). The user writes a change in plain words
  ("Shorten the summary to two sentences") and can limit it to the summary or one section, which the
  server enforces; the model picker defaults to the user's setting. The edit goes straight into the
  form and preview, autosave saves it, and Undo puts the CV back while nothing else has changed.
  Edits follow the no-new-facts rule: the fact guard checks them against the CV as it was, so a new
  number or claim (even one the user typed in the request) comes back as a placeholder to check, and
  the reply lists what the guard corrected. The model may also just answer a question about the CV.
  If the user edits the form while a request runs, the edit waits behind "Apply anyway". The content
  before an edit is kept as an autosave version. The conversation lasts while the editor is open.
- Placeholders render highlighted in preview. Export is blocked while placeholders remain, with a clear
  message and a "Show placeholders" action. (Export with placeholders is still possible from a
  secondary menu, labelled "Export anyway".)
- Version history: every tailoring, restore and explicit "Save version" creates a version; autosave
  snapshots are kept for 7 days. Users can preview and restore any version.
- Export: PDF download, named `<Name>-CV-<Company>.pdf` when a job is linked, else `<Name>-CV.pdf`.

Done when: a user can keep five CVs, edit one in form mode with live preview, switch templates without
losing content, eject another and edit its Typst, restore an earlier version, and export a PDF whose
text is selectable.

### 6. Templates

Five templates, all rendering the same data, all A4 and US Letter:

| ID | Name | Character |
|---|---|---|
| `classic` | Classic | Serif (Libertinus), centered header, navy section rules, muted tech stack beside the company name, dates and locations right-aligned, client engagements as sub-headings. |
| `compact` | Compact | Denser spacing and smaller type for long careers that must fit one page. |
| `modern` | Modern | Sans serif, left-aligned header, two-column header block, single-column body. |
| `minimal` | Minimal | Black and white only, generous whitespace, no rules. |
| `technical` | Technical | Monospace accents for stacks and dates, skills grid. |

- All templates are single-column in the body so text extraction and applicant tracking systems read them
  in order.
- Templates page shows a rendered preview of each using the user's default profile (fallback: fixture data)
  and lets the user set a default template.

Done when: every template compiles every fixture without errors, renders placeholders highlighted, and
the fixture CV fits one page in `classic` and `compact`.

### 7. Settings

- Account: name, email (read-only), sign out.
- AI: default model. Short explanation that every model works under the no-new-facts rule.
- Billing: current plan, usage this period, upgrade (Paystack checkout), manage subscription (Paystack
  hosted management link).
- Data: export everything as JSON; delete account (deletes all rows and stored files after typed
  confirmation of the email address).
- Appearance: theme (System, Light or Dark), saved in this browser. CV previews stay black on white.

Done when: changing the default model changes the preselected model on Import and Tailor, and
account deletion removes all user data from Postgres and GCS (verified by a test).

### 8. Browser extension

Applying is the step after tailoring. The Chameleon vitae extension for Chrome and Firefox fills job
application forms from the user's profiles and CVs, attaches a tailored CV as a PDF, and saves the
job ad the user is reading to Tailor. It lives in `apps/extension`.

- **The Extension page** (`/app/extension`, in the side nav) says what the extension does and what
  it can and cannot read, links to the browser stores once it is published there (until then it says
  it is not in the stores yet), and has two cards: This browser, and Connected browsers ("Chrome on
  macOS", connected and last used, with Disconnect).
- **Connect.** Installing opens the Extension page (a signed-out user signs in first and comes back
  to it). "Connect extension" makes a connection for this browser and hands its token to the
  extension, which checks it before keeping it. The extension's own Disconnect, and Disconnect on the
  Extension page, both revoke the token.
- **What it may do.** Read profiles and form-mode CVs, export a CV as PDF, and save jobs. It cannot
  change or delete anything and runs no AI, so it uses no AI usage.
- **Fill from** a profile or a CV, in a list. On the page of a saved job's ad or application form,
  the CV tailored for that job is chosen ("The CV you tailored for Data engineer at Harbour Bank");
  otherwise the user's last choice; otherwise the default profile.
- **Side panel.** The toolbar button opens it and lets the extension read that tab. Fill form reads
  the form in every frame (forms are often embedded) and shows a review: each field and the value it
  gets, grouped as Your details, Links, Role 1: <company>, School 1: <school>. Text values can be
  changed first; fields that have a value already are listed unticked. Notes say when the form has
  room for fewer roles than the profile ("Add another role in the form, then fill again"), which
  fields offer a list as you type, which texts were shortened to a field's length limit, and how many
  placeholders the source still has. Fill writes the ticked fields and marks them in the page until
  the user edits them; Undo fill puts the old values back.
- **Fill offer.** On known job platforms (Greenhouse, Lever, Workday, Ashby, SmartRecruiters,
  Workable and others) and on sites the user allowed from the panel, a small offer appears in the
  page's corner when an application form shows up, once per page or step: "Fill this application
  from your <source>? Nothing is sent until you submit it yourself." Nothing is read from the account
  until the user chooses Fill fields, and clicks made by the page's own scripts are ignored. The
  panel has a setting to turn the offer off.
- **Never** submits a form. Never fills equal opportunity questions (gender, race, veteran or
  disability status), work eligibility or sponsorship, pay, referrals, "how did you hear about us",
  cover letters, dates of birth or passwords, and never answers free-text questions. Never fills a
  text field the user cannot see (hidden, transparent, tiny or off the page), so a page cannot
  collect more than it shows. It adds
  nothing: a date the CV gives as a year fills only year fields, a missing middle name stays empty,
  and placeholders stay visible in their brackets.
- **Attach CV.** With a CV chosen, Attach CV puts its PDF into the form's CV upload, named
  `<Name>-CV-<Company>.pdf` when the CV was tailored for a job. Refused while the CV has placeholders,
  with an "Open in editor" action.
- **Save job ad.** Reads the ad from the page's job posting data (schema.org `JobPosting`), else the
  text the user selected, else the page. The user checks the title and company; Tailor a CV then
  opens Tailor with the job chosen (`/app/tailor?job=<id>`). Saving the same ad again keeps one job.
- **Copy your details.** Every detail with a copy button, for fields the extension cannot fill
  (custom lists and widgets).
- The browser keeps only the token, the account's email, the last choice and the offer setting.
  Profile and CV data is fetched when a form is filled and not stored.

Done when: in Chrome and Firefox a user installs the extension, connects it, fills the Greenhouse,
Lever, Workday and Ashby fixture forms from a profile after reviewing them, attaches a tailored CV,
saves a job ad and tailors for it, and disconnecting the browser on the Extension page stops the
extension at its next request.

## Plans and limits

Values live in one config module (`apps/api/src/api/billing/plans.py`) so they can change without code
changes elsewhere.

| Plan | Price | CVs | Profiles | AI runs per month |
|---|---|---|---|---|
| Free | 0 | 4 | 2 | 20 |
| Pro | Set in Paystack dashboard (monthly) | 100 | 10 | 150 |

- An AI run is one import, one job analysis, one tailoring or one AI edit request, regardless of
  model. Tailoring for a new job takes two runs (the analysis and the tailoring); tailoring a saved
  job again takes one.
- AI runs count per calendar month (UTC). On Free every attempt counts, failed ones included; on Pro
  only successful runs count.
- Free plans use the free models (MiMo Flash, Claude Haiku, Gemini Flash-Lite); Pro adds MiMo Pro,
  Gemini Flash and Claude Sonnet. Each model's plan is in `apps/api/src/api/ai/models.py`; it is
  enforced while `ENFORCE_AI_PLANS` is on (the default). New users start on MiMo Flash, the cheapest.
- Users never see run counts: the UI calls them **AI usage** and shows the share of the month's
  allowance used as a percentage ("15%"). Plans compare by multiple ("7 times the AI usage", Pro's
  allowance divided by Free's, rounded down).
- At the limit, the action is disabled with the message "You have used all of this month's AI usage.
  Upgrade to Pro for 7 times as much." (multiple from config).
- Downgrade keeps existing CVs readable and exportable but blocks creating new ones above the limit.
- Cancelling keeps Pro until the end of the paid period. A failed renewal keeps Pro until the paid
  period ends, then the user is on Free until a payment goes through.
- The side nav shows only the plan, no usage. Settings shows all three limits: AI usage as a
  percentage, CVs and profiles as counts ("2 of 4").

## Copy rules (summary; full rules in DESIGN.md)

Sentence case, plain words, no emojis, no exclamation marks, no hype ("magic", "supercharge").
Say what happened and what to do next.

## Out of scope for v1

Cover letters, LinkedIn import, DOCX export, collaboration and sharing links, mobile editing (mobile can
view and download), job board integrations (APIs; the browser extension works in the page), AI answers
to free-text application questions, analytics dashboards for users.
