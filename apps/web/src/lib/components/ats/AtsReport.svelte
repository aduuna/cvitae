<script lang="ts">
	import { BAND_LABELS, coverage, keywordGroups, titleLine } from '#lib/ats.ts';
	import Icon from '#lib/components/ui/Icon.svelte';
	import type { AtsKeyword, AtsReport } from '#lib/cv/types.ts';
	import KeywordChips from './KeywordChips.svelte';

	interface Props {
		report: AtsReport;
		/** What to do about keywords the profile lacks, where the report is shown. */
		notInProfileHint?: string;
		/** Show the checks that do not depend on the job. */
		checks?: boolean;
		/** Heading level of the groups, under the heading the report sits in. */
		level?: 3 | 4;
	}

	let {
		report,
		notInProfileHint = 'The job asks for these. Add the ones that are true to your profile.',
		checks = true,
		level = 4
	}: Props = $props();

	const groups = $derived(keywordGroups(report));
	const title = $derived(titleLine(report));
	const band = $derived(report.band ? BAND_LABELS[report.band] : null);
	const mustHaves = $derived(report.keywords.some((k) => k.importance === 'required'));
</script>

{#snippet group(heading: string, hint: string, keywords: AtsKeyword[])}
	{#if keywords.length > 0}
		<section class="flex flex-col items-start gap-2">
			<svelte:element this={`h${level}`} class="text-sm font-medium text-fg">
				{heading} ({keywords.length})
			</svelte:element>
			<p class="text-sm text-fg-muted">{hint}</p>
			<KeywordChips {keywords} label={heading} />
		</section>
	{/if}
{/snippet}

<div class="flex flex-col gap-5">
	{#if report.score === null || band === null}
		<p class="text-sm text-fg-muted">This job ad names no keywords to match.</p>
	{:else}
		<div class="flex flex-col gap-1.5">
			<div class="flex items-baseline justify-between gap-4">
				<p class="text-base font-medium text-fg">{band}</p>
				<p class="text-fg tabular-nums">
					<span class="text-xl font-semibold">{report.score}</span>
					<span class="text-sm text-fg-muted">/ 100</span>
				</p>
			</div>
			<div
				class="h-1 overflow-hidden rounded-sm bg-muted"
				role="meter"
				aria-label="ATS score"
				aria-valuemin={0}
				aria-valuemax={100}
				aria-valuenow={report.score}
				aria-valuetext="{report.score} of 100, {band}"
			>
				<div class="h-full rounded-sm bg-accent" style:width="{report.score}%"></div>
			</div>
			<p class="text-sm text-fg-muted">{coverage(report)} {title ?? ''}</p>
		</div>
	{/if}

	{@render group(
		'Left out of this CV',
		'Your profile has these. Put back the ones that fit this job.',
		groups.leftOut
	)}
	{@render group('Not in your profile', notInProfileHint, groups.notInProfile)}
	{@render group(
		'Not in this CV',
		'The job asks for these. Add the ones that are true.',
		groups.notInCv
	)}
	{@render group(
		'In this CV',
		groups.skillsOnly.length > 0
			? `Only in your skills list: ${groups.skillsOnly.map((k) => k.term).join(', ')}. Mention them in a role too, where true.`
			: 'Matched as written, ignoring case and plurals.',
		groups.found
	)}
	{#if mustHaves}
		<p class="text-sm text-fg-muted">Keywords in bold are must-haves in the job ad.</p>
	{/if}

	{#if checks && report.checks.length > 0}
		<section class="flex flex-col gap-2">
			<svelte:element this={`h${level}`} class="text-sm font-medium text-fg">
				Readability
			</svelte:element>
			<ul class="flex flex-col gap-1.5">
				{#each report.checks as check (check.id)}
					<li class={['flex gap-2 text-sm', check.ok ? 'text-fg-muted' : 'text-fg']}>
						<span class="mt-px">
							<Icon name={check.ok ? 'check-passed' : 'check-failed'} />
						</span>
						<span>
							<span class="sr-only">{check.ok ? 'Passed: ' : 'To fix: '}</span>{check.message}
						</span>
					</li>
				{/each}
			</ul>
		</section>
	{/if}

	<p class="text-xs text-fg-muted">
		Counts the job's keywords the way an ATS search reads this CV: whole words, as written. Each
		employer's system differs, so treat the score as a guide.
	</p>
</div>
