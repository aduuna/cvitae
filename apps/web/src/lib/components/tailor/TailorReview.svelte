<script lang="ts">
	import { onDestroy } from 'svelte';
	import { MediaQuery } from 'svelte/reactivity';
	import { modelLabel } from '#lib/ai/models.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import PreviewPanel from '#lib/components/editor/PreviewPanel.svelte';
	import Tabs from '#lib/components/ui/Tabs.svelte';
	import type { TailorResult } from '#lib/cv/types.ts';
	import { PreviewState } from '#lib/preview.svelte.ts';
	import NextSteps from './NextSteps.svelte';

	let { result }: { result: TailorResult } = $props();

	// The preview with next steps beside it on wide screens, two tabs on narrow ones
	// (DESIGN.md, Review screen).
	const wide = new MediaQuery('min-width: 1024px', true);
	let tab = $state('preview');

	const preview = $derived(new PreviewState(result.document.id));
	$effect(() => {
		void preview.refresh();
		return () => preview.dispose();
	});
	onDestroy(() => preview.dispose());

	const tabs = [
		{ id: 'preview', label: 'Preview' },
		{ id: 'next', label: 'Next steps' }
	];
</script>

{#snippet column(id: string)}
	{#if id === 'preview'}
		<div class="flex h-full min-h-120 flex-col overflow-hidden rounded-lg border border-line">
			<PreviewPanel {preview} />
		</div>
	{:else}
		<NextSteps {result} />
	{/if}
{/snippet}

<div class="flex min-h-0 flex-1 flex-col gap-4 p-6">
	<p class="text-sm text-fg-muted">
		Generated with {modelLabel(result.ai_model, session.aiModels)} for {result.job.title ||
			'this job'}{result.job.company ? ` at ${result.job.company}` : ''}.
	</p>
	{#if wide.current}
		<div class="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_22rem] gap-6">
			{#each tabs as column_ (column_.id)}
				<section aria-label={column_.label} class="flex min-h-0 flex-col gap-3 overflow-y-auto">
					<h2 class="text-lg font-semibold text-fg">{column_.label}</h2>
					{@render column(column_.id)}
				</section>
			{/each}
		</div>
	{:else}
		<Tabs {tabs} bind:value={tab} label="Review">
			{#snippet panel(id)}
				<div class="pt-4">{@render column(id)}</div>
			{/snippet}
		</Tabs>
	{/if}
</div>
