<script lang="ts">
	import Placeholder from '#lib/components/ui/Placeholder.svelte';
	import { parseRich } from '#lib/cv/richtext.ts';

	let { text }: { text: string } = $props();

	const spans = $derived(parseRich(text));
</script>

{#each spans as span, index (index)}{#if span.p}<Placeholder
			><span class={span.b ? 'font-semibold' : ''}>{span.t}</span></Placeholder
		>{:else if span.b}<strong class="font-semibold">{span.t}</strong>{:else}{span.t}{/if}{/each}
