# Chrome Web Store listing

What to paste into the Developer Dashboard. The images in this folder come from
`bun run store:assets` (the real extension against a mock account); run it again when the panel
changes.

## Store listing tab

- **Description:** the text below, as it is (the store shows plain text and keeps line breaks).
- **Category:** Workflow & Planning (or Tools).
- **Language:** English.
- **Store icon:** `public/icons/128.png`.
- **Screenshots:** `screenshot-1.jpg` to `screenshot-5.jpg`, in that order.
- **Small promo tile:** `promo-small.jpg`. **Marquee promo tile:** `promo-marquee.jpg`.
- **Global promo video:** leave empty.
- **Official URL / homepage:** https://cvitae.aduuna.dev
- **Support URL:** https://cvitae.aduuna.dev/privacy (or a support page, when there is one).

### Description

```text
Fill in job applications from your Chameleon vitae profile, instead of typing your CV into every careers site.

Chameleon vitae keeps your career history in one place and tailors your CV to each job without inventing anything. The extension helps with the step after that: the application form.

What it does
- Fills application forms from your profile or a tailored CV: your name, contact details, links, location, work history, education and skills.
- Shows you what will go where before anything is filled. Untick a field to leave it, or change its text first.
- Drafts answers to a form's open questions, such as "Why do you want to work here?", from your own experience and the job ad, with the AI model you chose in Chameleon vitae. You edit every draft, and see which skills it mentions that your profile does not name, before anything goes into the form.
- Chooses the CV you tailored for the job on the page, and attaches it to the form as a PDF.
- Saves the job ad you are reading to Chameleon vitae, so you can tailor a CV for it.
- Lists every detail with a copy button, for fields a site builds in its own way.
- Undo puts back what was there.

Where it works
It offers to fill forms on the applicant tracking systems many employers use for their careers pages. On any other careers site, open it from the toolbar, or allow the site once.

What it never does
- It never submits an application. You check every field and every answer, and send it yourself.
- It never answers equal opportunity, visa, salary or referral questions, and never fills a field you cannot see.
- It writes nothing into a form until you choose to fill.
- It cannot change or delete anything in your account.

Your data
The extension keeps only a connection key and your settings in the browser. Your profile is fetched when you choose to fill a form, and is not kept. It does not record the pages you visit. Page content leaves your browser only when you save a job ad, or when you ask for draft answers: then the questions you chose and the job ad go to Chameleon vitae, which sends them with your profile (without your email, phone or links) to the company behind your AI model. Neither the questions nor the drafts are stored. Drafting uses your plan's AI usage. Privacy policy: https://cvitae.aduuna.dev/privacy

You need a Chameleon vitae account. It is free to start: https://cvitae.aduuna.dev
```

## Privacy practices tab

**Single purpose:**

```text
Fill job application forms from the user's Chameleon vitae profile or tailored CV, including drafted answers to the form's open questions that the user edits and approves, attach that CV to the form, and save job ads to the user's Chameleon vitae account.
```

**Permission justifications:**

| Permission       | Justification                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `storage`        | Keeps the key that connects the extension to the user's account, the account's email, the profile or CV last chosen, and whether to offer filling. No profile or CV content is stored.                                                                                                                                                                                                |
| `activeTab`      | When the user clicks the toolbar button on a careers site, lets the extension read that tab's application form so it can fill it.                                                                                                                                                                                                                                                     |
| `scripting`      | Runs the extension's script in the job site's page (and its frames, where forms are often embedded) to read the form's fields and open questions, fill the ones the user approved, attach the CV and read the job ad when the user saves it or asks for draft answers.                                                                                                                |
| `sidePanel`      | Shows the extension's panel beside the application, where the user reviews what will be filled.                                                                                                                                                                                                                                                                                       |
| Host permissions | Known job application platforms (Greenhouse, Lever, Workday, Ashby and the others in the manifest), so the extension can offer to fill their forms without the toolbar button; and cvitae.aduuna.dev, the user's own account, which the extension connects to and which drafts answers when the user asks. Other sites are asked for one at a time, only when the user allows a site. |
| Remote code      | Choose "No, I am not using remote code". All code is in the package.                                                                                                                                                                                                                                                                                                                  |

**Data usage** (tick these two, leave the rest; the list shows on the install page):

- Personally identifiable information: name, email, phone and address (the city in the profile) from the user's own profile, to fill forms the user chooses to fill.
- Website content: the text of a job ad, when the user saves it; and the text of the application's open questions with the job ad, when the user asks for draft answers (sent to Chameleon vitae and, from there, to the AI provider the user chose; not stored).

Not the others: the connection key is issued by Chameleon vitae for itself, not credentials the
extension collects (Authentication information is for passwords and the like); the profile's city is
part of the address above, not the device's location; matching a page to a saved job happens in
the browser, so no web history leaves it; drafted answers come from Chameleon vitae to the panel,
they are not collected from the user. Drafting needs no new permission.

Then certify all three: not sold to third parties, not used or transferred for purposes unrelated to the item's single purpose, not used to determine creditworthiness or for lending.

**Privacy policy URL:** https://cvitae.aduuna.dev/privacy

Also, in the dashboard's account Settings: a contact email, then the link in the verification email
Google sends to it. The store will not publish without both.

## Test instructions tab

The review account is `cvitae-review`; `apps/api/scripts/review_account.py` creates it and prints
its password (each run sets a new one, so paste the latest in both stores). Before submitting, sign
in as it once at https://cvitae.aduuna.dev/login?password and add a profile, a CV and a CV tailored
to a Greenhouse or Lever job, so reviewers have something to fill from.

- **Username:** `cvitae-review@aduuna.dev`
- **Password:** the one the script printed.
- **Additional instructions:** below, with a live Greenhouse or Lever application link you checked
  in place of `<job link>` (job links expire, so check it on each submission). Pick one whose form
  has an open question, such as "Why do you want to work here?", so step 4 has something to draft.

```text
1. Sign in at https://cvitae.aduuna.dev/login?password with the username and password above (this page has the password form; the normal sign-in page offers Google and email links only).
2. Install the extension. It opens the app's Extension page; choose Connect extension.
3. Open a job application, for example <job link>, and click the extension's toolbar button. In the side panel choose Fill form, check the fields it lists, then choose Fill.
4. In the Answer questions card, the form's open questions are listed (or choose Find questions). Choose Draft answers, edit a draft if you like, then choose Fill. Drafting uses the account's AI usage; the account has plenty.
The extension never submits the form.
```

## addons.mozilla.org

- **Compatibility:** Firefox only. Leave Firefox for Android unticked: Android has no sidebar.
- **Description:** the same text as the Chrome description above. **Summary:** the manifest's
  description ("Fill job applications from your Chameleon vitae profile, draft answers to their
  questions, attach a tailored CV and save job ads.").
- **Data collection:** the manifest declares `personallyIdentifyingInfo` and `websiteContent` as
  required; drafted answers fit them (the questions and the job ad are website content), so they
  stay as they are.
- **Source code:** yes, upload `releases/cvitae-source-<version>.zip`.
- **Notes to reviewer:**

```text
Built with Vite from the uploaded source. To reproduce: install bun 1.3 and Node 24; run "bun install" in apps/web and in apps/extension; then in apps/extension run "VITE_APP_URL=https://cvitae.aduuna.dev bun run build". The add-on is dist/firefox. Nothing is minified. The side panel reuses the web app's components from apps/web.

To test, sign in at https://cvitae.aduuna.dev/login?password as cvitae-review@aduuna.dev with the password <the one the script printed>; that account has a profile and CVs to fill from. After installing, the add-on opens the app's Extension page; choose Connect extension, then open a job application, for example <job link>, and click the toolbar button to open the sidebar. Fill form fills the fields; in the Answer questions card, Draft answers sends the questions the user ticked and the job ad to the app's own api (cvitae.aduuna.dev), which drafts them with the user's AI model on the server and returns the drafts; nothing is sent before that click and nothing is written into the page before Fill. The add-on never submits the form.
```
