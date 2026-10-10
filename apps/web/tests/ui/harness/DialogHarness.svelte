<script lang="ts">
	import Button from '#lib/components/ui/Button.svelte';
	import Dialog from '#lib/components/ui/Dialog.svelte';
	import Input from '#lib/components/ui/Input.svelte';

	let { size = 'sm', onclose }: { size?: 'sm' | 'md'; onclose?: () => void } = $props();
	let open = $state(false);
</script>

<Button onclick={() => (open = true)}>Rename CV</Button>

<Dialog bind:open title="Rename CV" {size} {onclose}>
	<Input label="Name" />
	{#snippet footer()}
		<Button onclick={() => (open = false)}>Cancel</Button>
		<Button variant="primary">Save name</Button>
	{/snippet}
</Dialog>
