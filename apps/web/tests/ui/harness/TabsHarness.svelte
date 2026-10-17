<script lang="ts">
	import Tabs from '#lib/components/ui/Tabs.svelte';

	const tabs = [
		{ id: 'preview', label: 'Preview' },
		{ id: 'changes', label: 'Changes', icon: 'versions' as const },
		{ id: 'gaps', label: 'Gaps' }
	];

	let value = $state('preview');
</script>

<Tabs {tabs} bind:value label="Review">
	{#snippet panel(id)}
		<p>Panel {id}</p>
	{/snippet}
</Tabs>
