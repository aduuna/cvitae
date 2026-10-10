<script lang="ts">
	import Button from '#lib/components/ui/Button.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import { saveStatusText, type SaveState } from '#lib/autosave.svelte.ts';

	let { autosave }: { autosave: SaveState } = $props();
</script>

<!-- Autosave state for the top bar: "Saved", "Saving", or why saving failed with a retry. -->
<div class="flex items-center gap-2">
	<span
		role="status"
		title={autosave.error ?? undefined}
		class={[
			'inline-flex items-center gap-1 text-sm whitespace-nowrap',
			autosave.status === 'error' ? 'text-danger' : 'text-fg-muted'
		]}
	>
		{#if autosave.status === 'saved'}<Icon name="check" />{/if}
		{saveStatusText[autosave.status]}
	</span>
	{#if autosave.status === 'error'}
		<span class="sr-only">{autosave.error}</span>
		<Button size="sm" onclick={() => autosave.flush()}>Try again</Button>
	{/if}
</div>
