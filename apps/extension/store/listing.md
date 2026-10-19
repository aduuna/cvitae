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
- Chooses the CV you tailored for the job on the page, and attaches it to the form as a PDF.
- Saves the job ad you are reading to Chameleon vitae, so you can tailor a CV for it.
- Lists every detail with a copy button, for fields a site builds in its own way.
- Undo fill puts back what was there.

Where it works
It offers to fill forms on Greenhouse, Lever, Workday, Ashby, SmartRecruiters, Workable, BambooHR, iCIMS, Taleo, SuccessFactors, Avature, Jobvite, Recruitee, Teamtailor, Personio and Breezy HR. On any other careers site, open it from the toolbar, or allow the site once.

What it never does
- It never submits an application. You check every field and send it yourself.
- It never answers equal opportunity, visa, salary or referral questions, and never writes answers to free-text questions.
- It never fills a field you cannot see.
- It cannot change or delete anything in your account.

Your data
The extension keeps only a connection key and your settings in the browser. Your profile is fetched when you choose to fill a form, and is not kept. It does not record the pages you visit; page content leaves your browser only when you save a job ad. Privacy policy: https://cvitae.aduuna.dev/privacy

You need a Chameleon vitae account. It is free to start: https://cvitae.aduuna.dev
```

## Privacy practices tab

**Single purpose:**

```text
Fill job application forms from the user's Chameleon vitae profile or tailored CV, attach that CV to the form, and save job ads to the user's Chameleon vitae account.
```

**Permission justifications:**

| Permission       | Justification                                                                                                                                                                                                                                                                                  |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `storage`        | Keeps the key that connects the extension to the user's account, the account's email, the profile or CV last chosen, and whether to offer filling. No profile or CV content is stored.                                                                                                         |
| `activeTab`      | When the user clicks the toolbar button on a careers site, lets the extension read that tab's application form so it can fill it.                                                                                                                                                              |
| `scripting`      | Runs the extension's script in the job site's page (and its frames, where forms are often embedded) to read the form's fields, fill the ones the user approved, attach the CV and read the job ad when the user saves it.                                                                      |
| `sidePanel`      | Shows the extension's panel beside the application, where the user reviews what will be filled.                                                                                                                                                                                                |
| Host permissions | The job application platforms listed in the description, so the extension can offer to fill their forms without the toolbar button; and cvitae.aduuna.dev, the user's own account, which the extension connects to. Other sites are asked for one at a time, only when the user allows a site. |
| Remote code      | Choose "No, I am not using remote code". All code is in the package.                                                                                                                                                                                                                           |

**Data usage** (tick these two, leave the rest; the list shows on the install page):

- Personally identifiable information: name, email, phone and address (the city in the profile) from the user's own profile, to fill forms the user chooses to fill.
- Website content: the text of a job ad, only when the user saves it.

Not the others: the connection key is issued by Chameleon vitae for itself, not credentials the
extension collects (Authentication information is for passwords and the like); the profile's city is
part of the address above, not the device's location; matching a page to a saved job happens in
the browser, so no web history leaves it.

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
  in place of `<job link>` (job links expire, so check it on each submission).

```text
1. Sign in at https://cvitae.aduuna.dev/login?password with the username and password above (this page has the password form; the normal sign-in page offers Google and email links only).
2. Install the extension. It opens the app's Extension page; choose Connect extension.
3. Open a job application, for example <job link>, and click the extension's toolbar button. In the side panel choose Fill form, check the fields it lists, then choose Fill.
The extension never submits the form.
```

## addons.mozilla.org

- **Compatibility:** Firefox only. Leave Firefox for Android unticked: Android has no sidebar.
- **Source code:** yes, upload `releases/cvitae-source-<version>.zip`.
- **Notes to reviewer:**

```text
Built with Vite from the uploaded source. To reproduce: install bun 1.3 and Node 24; run "bun install" in apps/web and in apps/extension; then in apps/extension run "VITE_APP_URL=https://cvitae.aduuna.dev bun run build". The add-on is dist/firefox. Nothing is minified. The side panel reuses the web app's components from apps/web.

To test, sign in at https://cvitae.aduuna.dev/login?password as cvitae-review@aduuna.dev with the password <the one the script printed>; that account has a profile and CVs to fill from. After installing, the add-on opens the app's Extension page; choose Connect extension, then open a job application, for example <job link>, and click the toolbar button to open the sidebar. The add-on never submits the form.
```
