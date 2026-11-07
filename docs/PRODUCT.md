# Product spec

## One-line pitch

Paste a job description, get a CV tailored to it, typeset properly, without the AI inventing anything.

## Who it is for

Job seekers, mostly engineers and other technical professionals, who apply to many roles and want a
different CV for each. They care about typography, one-page discipline and honesty. Many are in Africa
and Europe, which is why payments go through Paystack.

## Core principles

1. **Your facts, better told.** In a CV the AI may select, reorder and reword what the user already
   said. It never adds employers, titles, dates, tools, numbers or achievements. Where a stronger bullet
   needs a number the user has not given, the CV shows a highlighted placeholder for the user to fill
   in. The fact guard checks every tailoring and AI edit against this rule.
2. **Structured data first, Typst second.** A user's career lives in a structured profile. CVs are views of
   that profile rendered through templates. Raw Typst editing is an advanced option, not the default.
3. **Fast and quiet.** Black and white UI, no clutter, live preview, keyboard friendly.
4. **Drafts the user finishes.** Answers to an application's open questions (8, Answer questions) are
   drafts the user edits before they are filled, not CV content. They follow a rule of their own:
   they may infer skills the user very likely has, and name them; they never invent employers, titles,
   dates, qualifications or numbers. Drafts are never saved and never go into a CV or a profile, so
   they cannot loosen the first principle.

## Glossary

| Term | Meaning |
|---|---|
| Profile | A user's master career data: contact details, roles, clients, bullets, skills, education, projects, certifications. A user can have several (for example "Data engineering" and "Backend"). |
| CV (document) | A renderable CV: a profile snapshot (possibly tailored), a template and a name. A user can have many. |
| Job | A saved job description with its title, company, URL and AI analysis. |
| Template | A Typst design that renders any CV. Five ship in v1; a user can add their own from a CV they like (6, Custom templates). |
| Custom template | A template made from the look of a CV the user uploads: Claude writes the Typst, the user previews it and keeps it next to the built-in ones. Only its owner sees it. |
| Placeholder | Highlighted text in a CV that the user must replace, for example "[[number of users]]". |
| Tailoring | Creating a CV from a profile plus a job, using AI under the no-new-facts rule. |
| AI edit | A change to one CV asked for in words in the editor's "Edit with AI" panel, under the same rule. |
| ATS score | How a CV reads to an applicant tracking system's keyword search for one job: 0 to 100, the job's keywords it covers and misses, and readability checks. |
| Ejected CV | A CV whose Typst source and data file the user edits directly. AI tailoring no longer applies to it. |
| Drafted answer | The extension's draft of an answer to an open question on an application form, from a profile or CV and the job ad. The user edits it before it is filled; it is never saved. |
| AI model | What runs an AI task: MiMo Flash, Claude Haiku or Gemini Flash-Lite on every plan; MiMo Pro, Gemini Flash or Claude Sonnet on Pro. |

## Navigation

A persistent left side nav with one item per feature. Each item is its own route with its own page.
Icons are Lucide, listed in `docs/DESIGN.md`.

| Order | Item | Route | Purpose |
|---|---|---|---|
| 1 | Documents | `/app/documents` | All CVs. Open, create, duplicate, rename, delete. Default landing page. |
| 2 | Profiles | `/app/profiles` | Enter and edit work experience and other career data. New profiles start at `/app/profiles/new`: import a CV (the default) or start from scratch. |
| 3 | Tailor | `/app/tailor` | Paste a job description and generate a tailored CV. Lists saved jobs. |
| 4 | Templates | `/app/templates` | Browse the 5 templates and your own with previews; set a default; add a template from a CV you like. |
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
  2. **ATS match**: the new CV's ATS score (see 9), with the job's keywords it covers, those it left
     out that the profile has, and those not in the profile (10 shown per group, "Show all" for the
     rest): "Add the ones that are true to your profile, then tailor again", and "Edit profile".
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
- ATS score: the top bar shows a form-mode CV's score for its job ("ATS 83", the score alone under
  1024px) and opens the ATS dialog (see 9). It follows every save.
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

#### Custom templates

A user who likes the look of a CV can have it as a template: they upload that CV as a PDF, Claude
writes a Typst template in its design, and the template then appears for that user, and only that
user, next to the five built-in ones. It renders their CVs like any other template.

- **Where.** The Templates page has a "Your templates" group after the built-in ones, with an "Add
  your own" card. Every template picker (new CV, Tailor, the editor's template switch, the default
  template in Templates) lists a user's own templates after the built-in ones.
- **Adding one.** The card opens a dialog: upload a PDF (the same upload as Import, and an earlier
  upload can be reused), a short explanation that this takes a little AI usage (one AI run), runs
  on Claude whatever model the user chose, and takes up to about two minutes, a progress state, then the result: a
  preview rendered with the user's default profile (or the sample), a name field, "Save template"
  and "Discard". Nothing is usable until "Save template"; discarding deletes it. A DOCX is refused
  with a clear message, because how a CV looks cannot be read from its text.
- **What Claude is asked for.** The design of the PDF: paper and margins, fonts as near as the
  bundled ones allow (Geist, Geist Mono, Libertinus Serif), sizes, colours, the header, section
  headings, how dates and locations align, bullets and spacing. The template still follows the
  template contract: one column in reading order (a sidebar in the original becomes part of the
  column), every part of the CV drawn, no images or logos, nothing of the uploaded CV's own content
  in it. Click to edit works in previews of a custom template as in a built-in one.
- **Checked before it is offered.** A draft that does not compile, breaks the contract, copies the
  uploaded CV's name, email, phone, links or text, drops any part of the sample CV's data or does not
  fit its page target is sent back to Claude with the problem, up to twice. One further pass shows
  Claude the original and the rendered result and asks it to match the design more closely; it is
  kept only when it passes the same checks. When a draft cannot be made to pass, nothing is saved and
  the user is told to try a simpler CV.
- **Using it.** A saved template is chosen like a built-in one, can be the default, and exports PDFs
  and drives the ATS page check as they do. Each custom card has the same live preview, "Set as
  default", rename, "View source" (the Typst, read only: it cannot be edited) and delete.
- **Deleting.** CVs that use the template switch to the user's default template, or to Classic when
  the default was this one. The default resets to Classic. The uploaded CV is kept like an import's.
- **Limits.** Free 1 custom template, Pro 10 (Plans and limits). Making one takes one AI run, however
  many corrections it needed; on Free a failed attempt counts, on Pro it does not. The limit and the
  AI usage are checked before Claude is called, so a refused request costs nothing. Without an
  Anthropic key the server cannot make templates, and the page does not offer "Add your own".
- **Privacy.** The uploaded CV is sent to Claude to draft the template and stored like an import's
  upload (privacy policy); the template's source is stored with the account and deleted with it.

Done when:

- Uploading the sample PDF in `templates/fixtures/` produces a draft whose preview shows the sample
  CV in that design, and saving it lists the template after the built-in ones in the Templates page
  and in the new CV, Tailor and editor pickers.
- A CV in the template previews, exports a PDF whose text is selectable and shows every part of the
  CV, and fits one page where its content does; switching it to a built-in template and back loses
  nothing.
- A template that does not compile, or copies the uploaded CV's name or text, is repaired or refused,
  and a refused generation saves nothing.
- A DOCX is refused with a clear message; the limit and the AI usage are checked before any model is
  called; a second user cannot preview, read, rename, delete or use the first user's template.
- Deleting a template moves its CVs to the default template, or to Classic.
- The dialog and the cards fit at 1280px and 768px.

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
application forms from the user's profiles and CVs, drafts answers to a form's open questions for the
user to edit, attaches a tailored CV as a PDF, and saves the job ad the user is reading to Tailor. It
lives in `apps/extension`.

- **The Extension page** (`/app/extension`, in the side nav) says what the extension does and what
  it can and cannot read, links to the browser stores once it is published there (until then it says
  it is not in the stores yet), and has two cards: This browser, and Connected browsers ("Chrome on
  macOS", connected and last used, with Disconnect).
- **Connect.** Installing opens the Extension page (a signed-out user signs in first and comes back
  to it). "Connect extension" makes a connection for this browser and hands its token to the
  extension, which checks it before keeping it. The extension's own Disconnect, and Disconnect on the
  Extension page, both revoke the token.
- **What it may do.** Read profiles and form-mode CVs, export a CV as PDF, save jobs, and draft
  answers to application questions, which spends AI usage (one AI run per request, see Answer
  questions). It cannot change or delete anything.
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
- **Never** submits a form. Never fills or drafts equal opportunity questions (gender, race, veteran
  or disability status), work eligibility or sponsorship, pay, referrals, "how did you hear about
  us", cover letters, dates of birth or passwords. An open question gets an answer only as a draft
  the user asked for, checked and chose to fill (Answer questions, below). Never fills a text field
  the user cannot see (hidden, transparent, tiny or off the page), so a page cannot collect more than
  it shows. Filling from a profile adds nothing: a date the CV gives as a year fills only year
  fields, a missing middle name stays empty, and placeholders stay visible in their brackets.
- **Attach CV.** With a CV chosen, Attach CV puts its PDF into the form's CV upload, named
  `<Name>-CV-<Company>.pdf` when the CV was tailored for a job. Refused while the CV has placeholders,
  with an "Open in editor" action.
- **Save job ad.** Reads the ad from the page's job posting data (schema.org `JobPosting`), else the
  text the user selected, else the page. The user checks the title and company; Tailor a CV then
  opens Tailor with the job chosen (`/app/tailor?job=<id>`). Saving the same ad again keeps one job.
- **Copy your details.** Every detail with a copy button, for fields the extension cannot fill
  (custom lists and widgets).
- The browser keeps only the token, the account's email, the last choice and the offer setting.
  Profile and CV data is fetched when a form is filled and not stored, and drafted answers live in
  the open panel only.

Done when: in Chrome and Firefox a user installs the extension, connects it, fills the Greenhouse,
Lever, Workday and Ashby fixture forms from a profile after reviewing them, attaches a tailored CV,
saves a job ad and tailors for it, and disconnecting the browser on the Extension page stops the
extension at its next request.

#### Answer questions

Many applications ask open questions ("Describe a time you used dbt in production", "Why do you
want to work here?"). The panel's Answer questions card drafts answers from the user's own material
so they can edit and fill them in seconds.

- **What a draft is made from.** The profile or CV chosen under Fill from (the CV tailored for this
  job when there is one, as for filling), and the job ad: the saved job when the page is one of its
  pages (its text and, once it was tailored for, its analysis), else the ad read from the page as
  Save job ad reads it, else none.
- **How drafts are written.** Useful beats cautious: the user reviews and edits every draft and knows
  what they actually did.
  - First person, plain and specific, set in the user's real roles, clients and projects, in the
    material's spelling convention. No cliches and no flattery of the employer.
  - A draft may expand on the material with reasonable inference. Someone whose CV shows Spark
    pipelines on Databricks has very likely used dbt, so a dbt question gets a confident answer set
    in those roles.
  - It never invents employers, clients, job titles, dates, degrees, certifications or other
    qualifications, or specific numbers. Where an answer needs a figure the material does not give,
    it has a placeholder such as "[[how many models]]". A number that is not in the material, the
    question or the job ad is turned into one ("[[check this number: 40]]") before the user sees it.
  - Questions about the company or role use the job ad; with no ad they get a placeholder such as
    "[[why this company]]".
  - Below each draft, one short line names the skills it mentions that are not in the material, and
    what in the material they rest on: "Mentions dbt, from your Spark and Databricks work." It is a
    hint of what to check, not a warning.
  - The CV fact guard does not run on drafts. Drafts never go into a CV, a profile or the database.
- **Finding questions.** Fill form, or Find questions in the card, reads the form in every frame. An
  open question is a visible, enabled text area, or a text field with room for a sentence (no length
  limit, or one of at least 100 characters), whose label reads as a question (it ends in "?", starts
  with a word such as why, what, how, describe, tell, explain, share or give, or runs to six words or
  more), and which filling from the profile does not already cover. Never listed: the questions
  under Never above, notice periods, start dates, relocation, references, years of experience,
  consent and signatures. Each shows its limit: the field's length limit, and a word or character
  limit its label or help text states ("in 200 words", "max 1,000 characters", "150 to 300 words"
  takes the upper bound). Questions that have a value already are listed unticked.
- **Before drafting.** Ticked questions are drafted; a line says what the drafts use ("From your Data
  engineering profile and the job ad you saved for Data engineer at Harbour Bank", "... and the job ad
  on this page", or "No job ad found here, so answers about the company will have gaps"). If the page
  says applicants must not use AI ("Do not use AI tools to write your answers"), a short notice above
  the list says so and quotes it. Drafting stays possible: the choice is the user's.
- **Drafts.** "Draft 3 answers" drafts every ticked question in one request. Each draft sits in an
  editable text box under its question, with a count against its limit ("143 of 200 words"), the
  skills hint, and Redraft, which writes a different draft of that one answer. A draft longer than
  its limit is cut at a sentence and marked Shortened; a single-line field gets one line. A question
  the AI leaves empty (one it must not answer) reads "Not drafted. Answer this one yourself." A note
  counts the placeholders still in square brackets. "Drafted with Claude Haiku."
- **Fill.** Nothing goes into the page until the user chooses "Fill 3 answers", which writes the
  ticked answers as filling does (cut to the field's length limit, marked until the user edits
  them). Undo puts back what the answers replaced, separately from the fields' Undo fill.
- **Privacy.** Only when the user chooses Draft answers or Redraft: the text and limits of those
  questions (with the draft it replaces, for Redraft), the job ad from the page (unless a saved job
  is used) and the chosen profile or CV go to the api, which sends them, without the user's email, phone and links, to the company behind the
  user's AI model. None of it is stored: not the questions, the ad read from the page, nor the
  drafts. The panel drops drafts when the tab or its page changes. The fill offer in the page never
  drafts.
- **AI model and usage.** The user's AI model from Settings. One AI run per Draft answers or Redraft,
  however many questions it covers, under the usual plan limits; at the limit the card shows the
  usual message. A Pro model on Free shows its message and Open settings.
- **Cover letters** are not drafted or filled: Chameleon vitae has no cover letters yet.

Done when: on the Greenhouse, Lever and Ashby fixtures and the custom careers page the card lists the
open questions and none of the excluded or hidden ones, with their limits; Draft answers (fake AI)
returns a draft for each within its limit, with the hint for a skill the profile does not name and a
placeholder for a number it does not give; the user edits one, unticks another, fills, and Undo puts
the fields back; one request uses one AI run; a page that bans AI shows the notice first.

### 9. ATS score

How a CV reads to an applicant tracking system's keyword search for one job. Real systems score a
CV against one opening (Workday HiredScore grades against the job's qualifications, Greenhouse
gives a match strength, Textkernel lists the terms found and not found), so there is no score
without a job, and none of them rejects a CV on its own: a recruiter does. The score is a guide to
what a search finds, not a prediction of any employer's result.

- **Per CV and job.** A CV has a score once it is linked to a job. Every tailored CV is; any other
  form-mode CV gets one in the ATS dialog by choosing a saved job ("Check against this job"). Linking
  also names the exported PDF for the job's company and makes it the CV the extension offers on that
  job's pages. A job that was never analysed (saved from the extension) is read first ("Read the job
  ad"): one AI run, once. The score itself takes no AI run, on any plan. Ejected CVs have none.
- **The score** (0 to 100) is the share of keyword points the CV covers, rounded down: a keyword
  the ad's must-haves name is worth 3, a nice-to-have 2, any other 1, and the job title 3. The
  title counts when the headline or a role title has it without seniority words ("Data Engineer"
  for "Senior Data Engineer, Payments Platform"). Bands: Strong match from 80, Good from 60,
  Partial from 40, else Limited.
- **Matching is literal, like a recruiter's search:** whole words, ignoring case, punctuation,
  plurals and British or American spelling, with a short list of known short forms (JS, K8s, AWS)
  and any "Full name (ABC)" the ad or the CV spells out. Placeholders do not count.
- **Keywords the CV misses** are looked up in the profile it came from: "Left out of this CV" (the
  profile has them: put back the ones that fit) and "Not in your profile" (add the ones that are
  true). "In this CV" names those found only in the skills list, since screeners look for them in
  the roles too. Must-haves show in bold.
- **Readability** (pass or fix, no score): email, phone and location in the header; section titles
  a parser recognises ("Experience", not "Where I have worked"); no placeholders left; within the
  template's page target. Columns, text boxes and fonts are not checked: every template is a single
  column of selectable text.
- The score never changes the CV and never suggests adding anything the person has not given.
- **Where:** the review screen after tailoring (Next steps, 2), and the editor's top bar, which
  opens the ATS dialog: the job and "Change job", the score, the keyword groups, readability.

Done when: the sample profile's CV against the fixture job scores 83 (Strong match, Snowflake and
Kubernetes not in the profile) in the API, the review screen shows the same report, a CV made from
a profile is linked to a saved job from the editor and shows its score, reading an unanalysed job
takes one AI run and never a second, and the dialog fits at 1280px and 768px.

## Plans and limits

Values live in one config module (`apps/api/src/api/billing/plans.py`) so they can change without code
changes elsewhere.

| Plan | Price | CVs | Profiles | Custom templates | AI runs per month |
|---|---|---|---|---|---|
| Free | 0 | 4 | 2 | 1 | 20 |
| Pro | Set in Paystack dashboard (monthly) | 100 | 10 | 10 | 150 |

- An AI run is one import, one job analysis, one tailoring, one AI edit request, one request for
  drafted answers (Draft answers or Redraft in the extension, however many questions it covers) or
  one custom template (however many corrections it took), regardless of model. Tailoring for a new
  job takes two runs (the analysis and the tailoring); tailoring a saved job again takes one. The ATS
  score takes none.
- AI runs count per calendar month (UTC). On Free every attempt counts, failed ones included; on Pro
  only successful runs count.
- Free plans use the free models (MiMo Flash, Claude Haiku, Gemini Flash-Lite); Pro adds MiMo Pro,
  Gemini Flash and Claude Sonnet. Each model's plan is in `apps/api/src/api/ai/models.py`; it is
  enforced while `ENFORCE_AI_PLANS` is on (the default). New users start on MiMo Flash, the cheapest.
- Custom templates always run on Claude, whatever model the user chose for other tasks, because how
  faithfully a design is copied and how good the Typst is matter most there: the user's own Claude
  model when they chose one, else Claude Sonnet on Pro and Claude Haiku on Free (the plan rule above
  still holds).
- Users never see run counts: the UI calls them **AI usage** and shows the share of the month's
  allowance used as a percentage ("15%"). Plans compare by multiple ("7 times the AI usage", Pro's
  allowance divided by Free's, rounded down).
- At the limit, the action is disabled with the message "You have used all of this month's AI usage.
  Upgrade to Pro for 7 times as much." (multiple from config).
- Downgrade keeps existing CVs readable and exportable but blocks creating new ones above the limit.
  Custom templates work the same way: those above the limit keep working, and no new one can be made.
- Cancelling keeps Pro until the end of the paid period. A failed renewal keeps Pro until the paid
  period ends, then the user is on Free until a payment goes through.
- The side nav shows only the plan, no usage. Settings shows all four limits: AI usage as a
  percentage, CVs, profiles and custom templates as counts ("2 of 4"). A template that is not yet
  saved does not count.

## Copy rules (summary; full rules in DESIGN.md)

Sentence case, plain words, no emojis, no exclamation marks, no hype ("magic", "supercharge").
Say what happened and what to do next.

## Out of scope for v1

Cover letters, LinkedIn import, DOCX export, collaboration and sharing links, mobile editing (mobile can
view and download), job board integrations (APIs; the browser extension works in the page), analytics
dashboards for users.
