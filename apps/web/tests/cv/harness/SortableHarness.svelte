<script lang="ts">
	import SortableList from '#lib/components/cv/SortableList.svelte';

	interface Row {
		id: string;
		text: string;
		children: { id: string; text: string }[];
	}

	let { initial }: { initial: Row[] } = $props();

	// Deeply reactive, like the content the app edits.
	// svelte-ignore state_referenced_locally
	let items = $state(initial);

	export function current(): Row[] {
		return $state.snapshot(items);
	}
</script>

<SortableList bind:items noun="role" label="Roles">
	{#snippet row(entry, index)}
		<input aria-label="Role {index + 1}" bind:value={entry.text} />
		<SortableList bind:items={entry.children} noun="bullet" label="Bullets for {entry.text}">
			{#snippet row(child, childIndex)}
				<input aria-label="{entry.text} bullet {childIndex + 1}" bind:value={child.text} />
			{/snippet}
		</SortableList>
	{/snippet}
</SortableList>
