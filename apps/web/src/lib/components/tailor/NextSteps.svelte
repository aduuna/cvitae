<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import Button from '#lib/components/ui/Button.svelte';
	import type { TailorResult } from '#lib/cv/types.ts';
	import ChangesPanel from './ChangesPanel.svelte';

	let { result }: { result: TailorResult } = $props();

	// What to do with a tailored CV, in order; the details of what changed stay folded away.
	const KEYWORDS_SHOWN = 10;
	let allKeywords = $state(false);

	const gaps = $derived(result.placeholders.length);
	const keywords = $derived(
		allKeywords ? result.missing_keywords : result.missing_keywords.slice(0, KEYWORDS_SHOWN)
	);
	const reworded = $derived(result.changes.filter((c) => c.text !== c.source_text).length);
	const summary = $derived(
		[
			`${reworded} reworded`,
			`${result.changes.length - reworded} kept as written`,
			result.dropped.length > 0 && `${result.dropped.length} left out`,
			result.issues.length > 0 && `${result.issues.length} corrected by the fact check`
		]
			.filter(Boolean)
			.join(', ')
	);
	const profileId = $derived(result.document.profile_id);
</script>

<div class="flex flex-col gap-6">
	<section aria-labelledby="gaps" class="flex flex-col items-start gap-2">
		<h3 id="gaps" class="text-base font-semibold text-fg">
			{gaps === 0 ? 'Nothing to fill in' : `Fill in ${gaps} ${gaps === 1 ? 'gap' : 'gaps'}`}
		</h3>
		{#if gaps === 0}
			<p class="text-sm text-fg-muted">Every detail comes from your profile.</p>
		{:else}
			<p class="text-sm text-fg-muted">
				They are highlighted in yellow. Replace each with a real detail, such as a number you can
				stand behind, then export.
			</p>
			<Button
				size="sm"
				onclick={() => goto(resolve('/app/documents/[id]', { id: result.document.id }))}
			>
				Fill in the editor
			</Button>
		{/if}
	</section>

	{#if result.missing_keywords.length > 0}
		<section aria-labelledby="keywords" class="flex flex-col items-start gap-2">
			<h3 id="keywords" class="text-base font-semibold text-fg">
				Not in your profile ({result.missing_keywords.length})
			</h3>
			<p class="text-sm text-fg-muted">
				The job asks for these. Add the ones that are true to your profile, then tailor again.
			</p>
			<ul class="flex flex-wrap gap-1.5" aria-label="Job keywords not in your profile">
				{#each keywords as keyword (keyword)}
					<li class="rounded-sm border border-line px-1.5 text-sm text-fg">{keyword}</li>
				{/each}
			</ul>
			<div class="flex items-center gap-2">
				{#if keywords.length < result.missing_keywords.length}
					<Button variant="ghost" size="sm" onclick={() => (allKeywords = true)}>
						Show all {result.missing_keywords.length}
					</Button>
				{/if}
				{#if profileId}
					<Button size="sm" onclick={() => goto(resolve('/app/profiles/[id]', { id: profileId }))}>
						Edit profile
					</Button>
				{/if}
			</div>
		</section>
	{/if}

	<details class="rounded-lg border border-line bg-surface">
		<summary class="cursor-pointer px-4 py-3 text-sm font-medium text-fg">
			What changed: {summary}
		</summary>
		<div class="border-t border-line p-4">
			<ChangesPanel changes={result.changes} dropped={result.dropped} issues={result.issues} />
		</div>
	</details>
</div>
