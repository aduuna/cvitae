<script lang="ts">
	import { resolve } from '$app/paths';
	import Logo from '#lib/components/shell/Logo.svelte';
	import { CONTACT_EMAIL, SITE_NAME, SITE_URL } from '#lib/site.ts';

	/** Change it whenever the policy changes. */
	const UPDATED = '18 October 2026';
	const mail = `mailto:${CONTACT_EMAIL}`;
</script>

<svelte:head>
	<title>Privacy policy - {SITE_NAME}</title>
	<meta
		name="description"
		content="What Chameleon vitae and its browser extension collect, why, who else handles it, and what you can do about it."
	/>
	<link rel="canonical" href="{SITE_URL}/privacy" />
</svelte:head>

{#snippet email()}
	<a href={mail} class="text-fg underline underline-offset-4">{CONTACT_EMAIL}</a>
{/snippet}

<div class="min-h-dvh bg-surface text-fg">
	<header class="border-b border-line">
		<div class="mx-auto flex h-14 w-full max-w-180 items-center px-4 sm:px-6">
			<a
				href={resolve('/')}
				class="flex items-center gap-2 rounded-md text-base font-semibold text-fg"
			>
				<Logo />
				{SITE_NAME}
			</a>
		</div>
	</header>

	<main
		id="main"
		class="mx-auto flex w-full max-w-180 flex-col gap-8 px-4 py-12 text-base text-fg sm:px-6"
	>
		<div class="flex flex-col gap-2">
			<h1 class="text-2xl font-semibold">Privacy policy</h1>
			<p class="text-sm text-fg-muted">Last updated {UPDATED}</p>
		</div>

		<p>
			Chameleon vitae keeps your career history in one place and turns it into a CV tailored to each
			job, and its browser extension fills job applications from it. This policy says what we
			collect, why, who else handles it, and what you can do about it. If anything is unclear, write
			to {@render email()}.
		</p>

		<section class="flex flex-col gap-3" aria-labelledby="collect">
			<h2 id="collect" class="text-lg font-semibold">What we collect</h2>
			<ul class="flex list-disc flex-col gap-2 pl-5">
				<li>
					<strong class="font-medium">Your account.</strong> Your email address, and the name you give,
					when you sign in with Google or an email link. Sign-in runs on Google's Firebase Authentication.
				</li>
				<li>
					<strong class="font-medium">What you put in.</strong> Your profiles, CVs, the job ads you save
					and the CV files you upload to import. This is what the service exists to work on.
				</li>
				<li>
					<strong class="font-medium">Records of use.</strong> For each AI task: which task and model,
					how many tokens it used, its cost, how long it took and whether it worked. Not what was sent
					or returned. We use them for plan limits and to watch costs.
				</li>
				<li>
					<strong class="font-medium">Payments.</strong> If you upgrade, Paystack takes the payment. We
					receive a customer code and your subscription's status and dates, never your card details.
				</li>
				<li>
					<strong class="font-medium">Technical logs.</strong> Request times, the parts of the app requested,
					and status and error codes, kept for up to 30 days to run and secure the service. We never log
					the content of your profiles, CVs, job ads, files or AI requests.
				</li>
			</ul>
			<p>We use no analytics, advertising or tracking tools, and we do not sell your data.</p>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="use">
			<h2 id="use" class="text-lg font-semibold">How we use it</h2>
			<p>
				Only to run the service for you: to keep and show your profiles and CVs, render them as
				PDFs, tailor and edit them when you ask, take payments, apply your plan's limits and keep
				the service secure. We do not train AI models on your data.
			</p>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="ai">
			<h2 id="ai" class="text-lg font-semibold">AI providers</h2>
			<p>
				When you import a CV, tailor a CV or ask for an edit, what that task needs (the CV, your
				profile, the job ad, your request) is sent to the company behind the AI model you choose:
				Xiaomi for MiMo models, Anthropic for Claude models, or Google for Gemini models. They
				process it to return the result, under their terms for business customers of their APIs. For
				Gemini we ask Google not to store the request.
			</p>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="extension">
			<h2 id="extension" class="text-lg font-semibold">The browser extension</h2>
			<ul class="flex list-disc flex-col gap-2 pl-5">
				<li>
					Connecting it gives it a key that works only for what the extension does: reading your
					profiles and CVs, exporting a CV as a PDF and saving job ads. It cannot change or delete
					anything.
				</li>
				<li>
					In your browser it keeps only that key, your account's email, the profile or CV you last
					chose and whether to offer filling. Your profiles and CVs are fetched when you fill a form
					and are not kept.
				</li>
				<li>
					On the job sites it supports, and on sites you allow, it looks for an application form so
					it can offer to fill it. It reads a form's fields, or the job ad, only when you choose
					Fill form, Fill fields, Attach CV or Save job ad.
				</li>
				<li>
					It does not record which pages you visit. Page content leaves your browser only when you
					save a job ad: the ad's title, company, address and text go to your account.
				</li>
				<li>
					It writes into a form only when you ask, and never submits it. What it fills is then
					shared with that site, as if you had typed it, under that site's own privacy policy.
				</li>
				<li>
					You can disconnect it at any time, from the extension or from the Extension page in the
					app. Removing the extension deletes what it kept in your browser.
				</li>
			</ul>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="others">
			<h2 id="others" class="text-lg font-semibold">Who else handles your data</h2>
			<ul class="flex list-disc flex-col gap-2 pl-5">
				<li>Google Cloud runs the service and stores uploaded files, in Belgium.</li>
				<li>Neon hosts the database.</li>
				<li>Google Firebase handles sign-in.</li>
				<li>Paystack handles payments.</li>
				<li>The company behind the AI model you choose, as described above.</li>
			</ul>
			<p>
				Some of them process data outside your country. We share data with authorities only when the
				law requires it.
			</p>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="keep">
			<h2 id="keep" class="text-lg font-semibold">How long we keep it</h2>
			<p>
				Your data stays while your account exists. You can delete profiles, CVs, saved jobs and
				uploaded files in the app at any time; a deleted file is removed from storage. To delete
				your account and everything in it, write to {@render email()} and we will do it within 30 days.
				Records of use go with the account; logs are kept for up to 30 days. Paystack keeps payment records
				for as long as the law requires.
			</p>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="rights">
			<h2 id="rights" class="text-lg font-semibold">Your rights</h2>
			<p>
				You can ask to see, correct, export or delete your data, or object to how we use it, by
				writing to {@render email()}. We answer within 30 days. You can also complain to the data
				protection authority where you live.
			</p>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="storage">
			<h2 id="storage" class="text-lg font-semibold">Cookies and browser storage</h2>
			<p>
				No advertising or analytics cookies. Your browser keeps your sign-in (stored by Firebase)
				and your choice of theme; the extension keeps what is listed above.
			</p>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="children">
			<h2 id="children" class="text-lg font-semibold">Children</h2>
			<p>The service is not meant for anyone under 16.</p>
		</section>

		<section class="flex flex-col gap-3" aria-labelledby="changes">
			<h2 id="changes" class="text-lg font-semibold">Changes</h2>
			<p>
				When this policy changes we update the date at the top, and we tell you by email when a
				change matters for how your data is used.
			</p>
		</section>
	</main>

	<footer class="border-t border-line">
		<div
			class="mx-auto flex w-full max-w-180 flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-fg-muted sm:px-6"
		>
			<a href={resolve('/')} class="rounded-md hover:text-fg">Home</a>
			<a href={mail} class="rounded-md hover:text-fg">{CONTACT_EMAIL}</a>
		</div>
	</footer>
</div>
