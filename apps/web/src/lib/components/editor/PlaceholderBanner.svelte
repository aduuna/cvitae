<script lang="ts">
	import Button from '#lib/components/ui/Button.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Placeholder from '#lib/components/ui/Placeholder.svelte';
	import { describeLocation } from '#lib/cv/locate.ts';
	import type { CvContent, PlaceholderRef } from '#lib/cv/types.ts';

	interface Props {
		placeholders: PlaceholderRef[];
		content: CvContent;
		onfocus: (ref: PlaceholderRef) => void;
		ondismiss: () => void;
	}

	let { placeholders, content, onfocus, ondismiss }: Props = $props();

	let expanded = $state(false);
	const count = $derived(placeholders.length);
</script>

<div role="status" class="rounded-lg border border-line bg-surface p-4">
	<div class="flex items-start gap-3">
		<span class="mt-0.5 text-fg"><Icon name="placeholder-warning" /></span>
		<div class="min-w-0 flex-1">
			<p class="text-base font-medium text-fg">
				Export stopped: this CV has {count}
				{count === 1 ? 'placeholder' : 'placeholders'} to fill in.
			</p>
			<p class="mt-0.5 text-sm text-fg-muted">
				Replace each one with a real detail and export again, or choose Export anyway from the menu
				next to Export PDF.
			</p>
		</div>
		<IconButton label="Dismiss" icon="close" size="sm" onclick={ondismiss} />
	</div>
	<div class="mt-3 pl-7">
		<Button size="sm" onclick={() => (expanded = !expanded)} aria-expanded={expanded}>
			{expanded ? 'Hide placeholders' : 'Show placeholders'}
		</Button>
		{#if expanded}
			<ul class="mt-2 flex flex-col gap-1" aria-label="Placeholders">
				{#each placeholders as ref, index (index)}
					<li>
						<button
							type="button"
							class="flex w-full flex-wrap items-center gap-x-2 gap-y-1 rounded-md px-2 py-1.5 text-left hover:bg-subtle"
							onclick={() => onfocus(ref)}
						>
							<Placeholder>{ref.text}</Placeholder>
							<span class="text-sm text-fg-muted">{describeLocation(content, ref)}</span>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>
