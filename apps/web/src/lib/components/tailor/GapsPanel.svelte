<script lang="ts">
	import Placeholder from '#lib/components/ui/Placeholder.svelte';
	import type { PlaceholderRef } from '#lib/cv/types.ts';

	interface Props {
		placeholders: PlaceholderRef[];
		missingKeywords: string[];
	}

	let { placeholders, missingKeywords }: Props = $props();
</script>

<div class="flex flex-col gap-6">
	<section>
		<h3 class="text-base font-semibold text-fg">Fill in</h3>
		{#if placeholders.length === 0}
			<p class="mt-1 text-sm text-fg-muted">Nothing to fill in.</p>
		{:else}
			<p class="mt-1 text-sm text-fg-muted">
				Replace these in the editor before exporting. Only use numbers you can stand behind.
			</p>
			<ul class="mt-3 flex flex-col gap-2 text-base">
				{#each placeholders as placeholder, index (index)}
					<li><Placeholder>{placeholder.text}</Placeholder></li>
				{/each}
			</ul>
		{/if}
	</section>

	<section>
		<h3 class="text-base font-semibold text-fg">Not in your profile</h3>
		{#if missingKeywords.length === 0}
			<p class="mt-1 text-sm text-fg-muted">Your profile covers the job's keywords.</p>
		{:else}
			<p class="mt-1 text-sm text-fg-muted">
				The job asks for these and your profile does not mention them. Only add these if they are
				true.
			</p>
			<ul class="mt-3 flex flex-wrap gap-1.5">
				{#each missingKeywords as keyword (keyword)}
					<li class="rounded-sm border border-line px-1.5 text-sm text-fg">{keyword}</li>
				{/each}
			</ul>
		{/if}
	</section>
</div>
