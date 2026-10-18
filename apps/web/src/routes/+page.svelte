<script lang="ts">
	import { onMount } from 'svelte';
	import { resolve } from '$app/paths';
	import { session } from '#lib/auth/session.svelte.ts';
	import Cartoon, { type cartoons } from '#lib/components/landing/Cartoon.svelte';
	import EditShot from '#lib/components/landing/EditShot.svelte';
	import EditorShot from '#lib/components/landing/EditorShot.svelte';
	import ExportShot from '#lib/components/landing/ExportShot.svelte';
	import FlowStep from '#lib/components/landing/FlowStep.svelte';
	import ImportShot from '#lib/components/landing/ImportShot.svelte';
	import ProfilesShot from '#lib/components/landing/ProfilesShot.svelte';
	import TailorShot from '#lib/components/landing/TailorShot.svelte';
	import Logo from '#lib/components/shell/Logo.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import type { IconName } from '#lib/components/ui/icons.ts';
	import LinkButton from '#lib/components/ui/LinkButton.svelte';
	import { SITE_DESCRIPTION, SITE_NAME, SITE_TITLE, SITE_URL, structuredData } from '#lib/site.ts';

	// The page is prerendered for visitors (and search engines). Once it runs in the browser,
	// signed-in users get a way into the app instead of the sign-in links.
	let hydrated = $state(false);
	onMount(() => (hydrated = true));
	const signedIn = $derived(hydrated && session.status === 'signed-in');

	const principles: { icon: IconName; title: string; body: string }[] = [
		{
			icon: 'facts',
			title: 'Checked against your facts',
			body: 'Tailoring selects, reorders and rewords what you wrote. A number that is not in your source becomes a placeholder, and every change sits next to the original so you can check it.'
		},
		{
			icon: 'typeset',
			title: 'Typeset with Typst',
			body: 'Each CV compiles to a real PDF with proper typography and one-page discipline. Five templates, and the source is yours when you want it.'
		},
		{
			icon: 'model',
			title: 'Your choice of model',
			body: 'Run imports and tailoring on MiMo, Claude or Gemini. Not happy with a draft? Regenerate it with another model.'
		}
	];

	const features: { cartoon: keyof typeof cartoons; title: string; body: string }[] = [
		{
			cartoon: 'cover-letter',
			title: 'Cover letters in your tone',
			body: 'Download a cover letter for each job, written from your profile and matched to the tone of cover letters you have uploaded.'
		},
		{
			cartoon: 'extension',
			title: 'Fill in applications faster',
			body: 'A Chrome extension that fills in application forms on careers sites from your profile, so you stop retyping your CV into every form.'
		},
		{
			cartoon: 'ats',
			title: 'ATS score',
			body: "See how your CV reads to applicant tracking systems before you send it: a score, the job's keywords you cover and the ones you miss."
		}
	];
</script>

<svelte:head>
	<title>{SITE_TITLE}</title>
	<meta name="description" content={SITE_DESCRIPTION} />
	<link rel="canonical" href="{SITE_URL}/" />
	<meta property="og:type" content="website" />
	<meta property="og:url" content="{SITE_URL}/" />
	<meta property="og:site_name" content={SITE_NAME} />
	<meta property="og:title" content={SITE_TITLE} />
	<meta property="og:description" content={SITE_DESCRIPTION} />
	<meta property="og:image" content="{SITE_URL}/og.png" />
	<meta property="og:image:width" content="1200" />
	<meta property="og:image:height" content="630" />
	<meta property="og:image:alt" content="Chameleon vitae: one career, a CV for every job." />
	<meta name="twitter:card" content="summary_large_image" />
	<!-- eslint-disable-next-line svelte/no-at-html-tags -- static structured data from $lib/site.ts, no user input -->
	{@html structuredData()}
</svelte:head>

{#snippet primaryAction()}
	{#if signedIn}
		<LinkButton href={resolve('/app/documents')} variant="primary" size="lg">Open app</LinkButton>
	{:else}
		<LinkButton href={resolve('/login')} variant="primary" size="lg">Get started</LinkButton>
	{/if}
{/snippet}

<div class="min-h-dvh bg-surface text-fg">
	<header class="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur-sm">
		<div class="mx-auto flex h-14 w-full max-w-280 items-center justify-between gap-4 px-4 sm:px-6">
			<a
				href={resolve('/')}
				class="flex items-center gap-2 rounded-md text-base font-semibold text-fg"
			>
				<Logo />
				Chameleon vitae
			</a>
			<nav aria-label="Site" class="flex items-center gap-2">
				<a
					href="#how-it-works"
					class="hidden rounded-md px-3 py-1.5 text-base text-fg-muted transition-colors duration-120 ease-out hover:text-fg sm:inline"
				>
					How it works
				</a>
				{#if signedIn}
					<LinkButton href={resolve('/app/documents')} variant="primary">Open app</LinkButton>
				{:else}
					<LinkButton href={resolve('/login')}>Sign in</LinkButton>
				{/if}
			</nav>
		</div>
	</header>

	<main id="main">
		<section class="border-b border-line">
			<div
				class="mx-auto grid w-full max-w-280 items-center gap-10 px-4 py-14 sm:px-6 md:grid-cols-2 md:py-20 lg:gap-16"
			>
				<div class="flex flex-col items-start gap-6">
					<h1 class="text-3xl font-semibold tracking-tight text-fg lg:text-4xl">
						<span class="block">One career,</span>
						<span class="block">a CV for every job</span>
					</h1>
					<p class="max-w-120 text-lg text-fg-muted">
						Chameleon vitae adapts your CV to every job you apply to, like a chameleon. Import your
						CV once, paste a job description and get a version that leads with what that job asks
						for. The AI picks, reorders and rewords what you wrote, and you review every change.
					</p>
					<div class="flex flex-wrap items-center gap-x-6 gap-y-3">
						{@render primaryAction()}
						<a
							href="#how-it-works"
							class="inline-flex items-center gap-1.5 rounded-md text-base font-medium text-fg underline-offset-4 hover:underline"
						>
							See how it works
							<Icon name="chevron-down" />
						</a>
					</div>
				</div>
				<div class="mx-auto w-full max-w-120 md:max-w-none">
					<Cartoon
						name="tailor"
						label="A chameleon on a pencil picks a bullet that fits the pinned job and places it in the CV."
					/>
				</div>
			</div>
		</section>

		<div class="bg-canvas">
			<div class="mx-auto w-full max-w-280 px-4 py-14 sm:px-6 md:py-16">
				<EditorShot />
			</div>
		</div>

		<section
			id="how-it-works"
			aria-labelledby="how-it-works-title"
			class="scroll-mt-14 border-t border-line"
		>
			<div class="mx-auto w-full max-w-280 px-4 py-20 sm:px-6">
				<div class="flex max-w-150 flex-col gap-3">
					<p class="font-mono text-sm text-fg-muted">How it works</p>
					<h2
						id="how-it-works-title"
						class="text-2xl font-semibold tracking-tight text-fg sm:text-3xl"
					>
						From the CV you have to the CV each job needs
					</h2>
					<p class="text-lg text-fg-muted">
						Five steps. The AI does the slow parts, and you check everything it does.
					</p>
				</div>

				<ol class="mt-14 flex flex-col">
					<FlowStep step={1} icon="import" title="Import your CV">
						<p>
							Upload a PDF or Word file, or paste the text. The AI model you choose reads it into a
							structured profile: roles, clients, bullets, skills and education.
						</p>
						<p>
							You review every entry before it is saved. Anything your CV does not say stays empty.
						</p>
						{#snippet shot()}<ImportShot />{/snippet}
					</FlowStep>

					<FlowStep step={2} icon="profiles" title="Keep a profile for each direction">
						<p>
							A profile is your career history in one place. Keep one for data engineering and
							another for backend roles, and mark the one you use most as the default.
						</p>
						<p>Edits save as you type, and each profile can feed many CVs.</p>
						{#snippet shot()}<ProfilesShot />{/snippet}
					</FlowStep>

					<FlowStep step={3} icon="tailor" title="Tailor it to the job">
						<p>
							Paste a job description. You get a new CV that leads with your most relevant
							experience, reworded in the job's language.
						</p>
						<p>
							Every change sits under the bullet it came from. Where a stronger bullet needs a
							number you have not given, it asks for it with a highlighted placeholder to fill in.
						</p>
						{#snippet shot()}<TailorShot />{/snippet}
					</FlowStep>

					<FlowStep step={4} icon="form" title="Edit the CV">
						<p>
							Edit in a form next to a live preview, and switch between 5 templates at any time.
							Changes stay in this CV and leave your profile as it was.
						</p>
						<p>For full control, switch the CV to Typst and edit its source directly.</p>
						{#snippet shot()}<EditShot />{/snippet}
					</FlowStep>

					<FlowStep step={5} icon="download" title="Export the PDF">
						<p>
							Download a PDF named for you and the company, ready to attach. Export checks that
							every placeholder is filled first, so a gap never goes out by accident.
						</p>
						{#snippet shot()}<ExportShot />{/snippet}
					</FlowStep>
				</ol>
			</div>
		</section>

		<section aria-labelledby="principles-title" class="border-t border-line">
			<div class="mx-auto w-full max-w-280 px-4 py-20 sm:px-6">
				<h2
					id="principles-title"
					class="max-w-150 text-2xl font-semibold tracking-tight text-fg sm:text-3xl"
				>
					Your facts, better told
				</h2>
				<ul class="mt-10 grid gap-8 md:grid-cols-3 md:gap-6">
					{#each principles as principle (principle.title)}
						<li class="flex flex-col gap-3 border-t border-line pt-6">
							<span
								class="flex size-9 items-center justify-center rounded-md bg-muted text-fg"
								aria-hidden="true"
							>
								<Icon name={principle.icon} />
							</span>
							<h3 class="text-lg font-semibold text-fg">{principle.title}</h3>
							<p class="text-base text-fg-muted">{principle.body}</p>
						</li>
					{/each}
				</ul>
			</div>
		</section>

		<section aria-labelledby="more-help-title" class="border-t border-line">
			<div class="mx-auto w-full max-w-280 px-4 py-20 sm:px-6">
				<div class="flex max-w-150 flex-col gap-3">
					<p class="font-mono text-sm text-fg-muted">Beyond the CV</p>
					<h2
						id="more-help-title"
						class="text-2xl font-semibold tracking-tight text-fg sm:text-3xl"
					>
						More help with every application
					</h2>
					<p class="text-lg text-fg-muted">
						Built on the same profiles and jobs you already keep here.
					</p>
				</div>
				<ul class="mt-10 grid gap-6 md:grid-cols-3">
					{#each features as feature (feature.title)}
						<li class="flex flex-col overflow-hidden rounded-lg border border-line bg-surface">
							<div class="border-b border-line bg-canvas px-8 py-6">
								<Cartoon name={feature.cartoon} />
							</div>
							<div class="flex flex-col gap-2 p-5">
								<h3 class="text-lg font-semibold text-fg">{feature.title}</h3>
								<p class="text-base text-fg-muted">{feature.body}</p>
							</div>
						</li>
					{/each}
				</ul>
			</div>
		</section>

		<section aria-labelledby="get-started-title" class="border-t border-line bg-canvas">
			<div
				class="mx-auto flex w-full max-w-280 flex-col items-center gap-6 px-4 py-20 text-center sm:px-6"
			>
				<div class="w-52">
					<Cartoon name="stack" />
				</div>
				<h2
					id="get-started-title"
					class="mt-4 text-2xl font-semibold tracking-tight text-balance text-fg sm:text-3xl"
				>
					Start with the CV you already have
				</h2>
				<p class="max-w-120 text-lg text-fg-muted">
					Import it once, then tailor a version for each job you apply to.
				</p>
				<div class="flex flex-col items-center gap-3">
					{@render primaryAction()}
					{#if !signedIn}
						<p class="text-sm text-fg-muted">Your first sign-in creates your account.</p>
					{/if}
				</div>
			</div>
		</section>
	</main>

	<footer class="border-t border-line">
		<div
			class="mx-auto flex w-full max-w-280 flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-fg-muted sm:px-6"
		>
			<span class="flex items-center gap-2 font-medium text-fg">
				<Logo />
				Chameleon vitae
			</span>
			<a
				href={resolve('/login')}
				class="rounded-md transition-colors duration-120 ease-out hover:text-fg"
			>
				Sign in
			</a>
		</div>
	</footer>
</div>
