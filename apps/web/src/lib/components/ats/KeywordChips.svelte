<script lang="ts">
	import Button from '#lib/components/ui/Button.svelte';
	import type { AtsKeyword } from '#lib/cv/types.ts';

	interface Props {
		keywords: AtsKeyword[];
		/** Names the list for screen readers. */
		label: string;
		/** How many show before "Show all". */
		shown?: number;
	}

	let { keywords, label, shown = 10 }: Props = $props();

	let all = $state(false);
	const visible = $derived(all ? keywords : keywords.slice(0, shown));

	function showAll() {
		all = true;
	}
</script>

<ul class="flex flex-wrap gap-1.5" aria-label={label}>
	{#each visible as keyword (keyword.term)}
		<li
			class={[
				'rounded-sm border px-1.5 text-sm text-fg',
				keyword.importance === 'required' ? 'border-line-strong font-medium' : 'border-line'
			]}
		>
			{keyword.term}
			{#if keyword.importance === 'required'}
				<span class="sr-only">(must-have)</span>
			{/if}
		</li>
	{/each}
</ul>
{#if visible.length < keywords.length}
	<div>
		<Button variant="ghost" size="sm" onclick={showAll}>Show all {keywords.length}</Button>
	</div>
{/if}
