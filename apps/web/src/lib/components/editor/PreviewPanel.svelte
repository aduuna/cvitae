<script lang="ts">
	import SegmentedControl from '#lib/components/ui/SegmentedControl.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { formatPages } from '#lib/format.ts';
	import { pageWidthPx, svgDataUrl, type PreviewState } from '#lib/preview.svelte.ts';

	type Zoom = 'fit' | '75' | '100' | '125';

	let { preview }: { preview: PreviewState } = $props();

	const zoomOptions: { value: Zoom; label: string }[] = [
		{ value: 'fit', label: 'Fit' },
		{ value: '75', label: '75%' },
		{ value: '100', label: '100%' },
		{ value: '125', label: '125%' }
	];

	// Canvas padding on each side (p-6).
	const GUTTER = 24;

	let zoom = $state<Zoom>('fit');
	let canvasWidth = $state(0);

	function width(svg: string): number {
		const natural = pageWidthPx(svg);
		if (zoom === 'fit') return Math.max(200, canvasWidth - GUTTER * 2);
		return Math.round((natural * Number(zoom)) / 100);
	}

	const status = $derived(
		preview.loading && preview.pages.length === 0
			? 'Rendering'
			: preview.pageCount
				? formatPages(preview.pageCount)
				: ''
	);
</script>

<section aria-label="Preview" class="flex h-full min-h-0 flex-col bg-canvas">
	<div
		class="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line bg-surface px-3"
	>
		<p class="text-sm text-fg-muted tabular-nums" aria-live="polite">
			{status}{#if preview.loading && preview.pages.length > 0}<span class="sr-only"
					>, updating</span
				>{/if}
		</p>
		<SegmentedControl label="Zoom" options={zoomOptions} bind:value={zoom} />
	</div>

	{#if preview.diagnostics.length > 0}
		<div role="alert" class="shrink-0 border-b border-danger bg-surface px-4 py-3">
			<p class="text-base font-medium text-danger">
				The CV could not be rendered. The last good preview is shown.
			</p>
			<ul class="mt-1 flex flex-col gap-0.5">
				{#each preview.diagnostics as diagnostic, index (index)}
					<li class="font-mono text-sm text-fg">
						{#if diagnostic.line}<span class="text-fg-muted"
								>{diagnostic.file ?? 'main.typ'}:{diagnostic.line}:{diagnostic.column ?? 1}</span
							>
						{/if}{diagnostic.message}
					</li>
				{/each}
			</ul>
		</div>
	{:else if preview.error}
		<div role="alert" class="shrink-0 border-b border-danger bg-surface px-4 py-3">
			<p class="text-base text-danger">{preview.error}</p>
		</div>
	{/if}

	<div class="min-h-0 flex-1 overflow-auto p-6" bind:clientWidth={canvasWidth}>
		{#if preview.pages.length === 0}
			{#if preview.loading}
				<div class="mx-auto max-w-140"><Skeleton variant="block" height="lg" /></div>
			{/if}
		{:else}
			<div class="flex w-max min-w-full flex-col items-center gap-6">
				{#each preview.pages as svg, index (index)}
					<img
						src={svgDataUrl(svg)}
						alt="Page {index + 1} of {preview.pages.length}"
						style:width="{width(svg)}px"
						class="block max-w-none bg-surface shadow-page"
						draggable="false"
					/>
				{/each}
			</div>
		{/if}
	</div>
</section>
