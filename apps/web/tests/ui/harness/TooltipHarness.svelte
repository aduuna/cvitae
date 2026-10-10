<script lang="ts">
	import Tooltip from '#lib/components/ui/Tooltip.svelte';

	let { describe = true, disabled = false }: { describe?: boolean; disabled?: boolean } = $props();
</script>

<Tooltip text="Copy link" {describe} {disabled}>
	{#snippet children(trigger)}
		<button type="button" {...trigger}>Share</button>
	{/snippet}
</Tooltip>
