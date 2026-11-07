<script lang="ts">
	import Tabs from '#lib/components/ui/Tabs.svelte';

	let { fill = false }: { fill?: boolean } = $props();

	const tabs = [
		{ id: 'preview', label: 'Preview' },
		{ id: 'changes', label: 'Changes', icon: 'versions' as const },
		{ id: 'gaps', label: 'Gaps' }
	];

	let value = $state('preview');
</script>

<Tabs {tabs} bind:value label="Review" {fill}>
	{#snippet panel(id)}
		<p>Panel {id}</p>
	{/snippet}
</Tabs>
