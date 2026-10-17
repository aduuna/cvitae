<script lang="ts">
	import type { Snippet } from 'svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';

	interface Props {
		/** The item's id: a click on its part of the preview opens this panel. */
		id: string;
		/** What the item is, from its fields; falls back to `placeholder` while empty. */
		title: string;
		placeholder: string;
		deleteLabel: string;
		ondelete: () => void;
		children: Snippet;
	}

	let { id, title, placeholder, deleteLabel, ondelete, children }: Props = $props();
</script>

<div data-cv-id={id} class="@container rounded-md border border-line bg-surface">
	<div class="flex items-center justify-between gap-2 border-b border-line py-1 pr-1 pl-3">
		<p class={['truncate text-sm font-medium', title.trim() ? 'text-fg' : 'text-fg-muted']}>
			{title.trim() || placeholder}
		</p>
		<IconButton label={deleteLabel} icon="delete" size="sm" onclick={ondelete} />
	</div>
	<div class="flex flex-col gap-3 p-3">
		{@render children()}
	</div>
</div>
