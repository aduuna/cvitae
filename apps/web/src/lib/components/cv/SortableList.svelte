<script lang="ts" generics="T extends object">
	import { tick, type Snippet } from 'svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import { moveItem } from '#lib/cv/factory.ts';

	interface Props {
		items: T[];
		/** Singular noun for handle labels and announcements, for example "bullet". */
		noun: string;
		/** Accessible name of the list, for example "Bullets for Acme". */
		label: string;
		/** One item's content; the drag handle sits before it. */
		row: Snippet<[T, number]>;
		/** Stable key per item; defaults to its `id`. */
		key?: (item: T) => string;
		gap?: 'sm' | 'md';
		disabled?: boolean;
	}

	let {
		items = $bindable(),
		noun,
		label,
		row,
		key = (item) => (item as { id: string }).id,
		gap = 'md',
		disabled = false
	}: Props = $props();

	let dragFrom = $state<number | null>(null);
	let dropAt = $state<{ index: number; after: boolean } | null>(null);
	let announcement = $state('');

	function move(from: number, to: number) {
		if (moveItem(items, from, to)) {
			announcement = `Moved ${noun} to position ${to + 1} of ${items.length}.`;
		}
	}

	// Alt+Up and Alt+Down move the item holding focus. The innermost list handles the keys, so a
	// bullet moves within its role rather than moving the role.
	async function onkeydown(event: KeyboardEvent, index: number) {
		if (disabled || !event.altKey || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) {
			return;
		}
		event.preventDefault();
		event.stopPropagation();
		const focused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
		move(index, event.key === 'ArrowUp' ? index - 1 : index + 1);
		await tick();
		focused?.focus();
	}

	function ondragstart(event: DragEvent, index: number) {
		event.stopPropagation();
		dragFrom = index;
		const transfer = event.dataTransfer;
		if (!transfer) return;
		transfer.effectAllowed = 'move';
		transfer.setData('text/plain', `${noun} ${index + 1}`);
		const row = (event.currentTarget as HTMLElement).closest('li');
		if (row) transfer.setDragImage(row, 16, 16);
	}

	function ondragover(event: DragEvent, index: number) {
		// Drags that started in another list bubble on to that list.
		if (dragFrom === null) return;
		event.preventDefault();
		event.stopPropagation();
		const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
		dropAt = { index, after: event.clientY > rect.top + rect.height / 2 };
	}

	function ondrop(event: DragEvent) {
		if (dragFrom === null || dropAt === null) return;
		event.preventDefault();
		event.stopPropagation();
		let to = dropAt.after ? dropAt.index + 1 : dropAt.index;
		if (dragFrom < to) to -= 1;
		move(dragFrom, to);
		reset();
	}

	function reset() {
		dragFrom = null;
		dropAt = null;
	}
</script>

<ul aria-label={label} class={['flex flex-col', gap === 'sm' ? 'gap-2' : 'gap-3']}>
	{#each items as entry, index (key(entry))}
		<!-- The row only delegates key and drop events from the controls inside it. -->
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<li
			class={['relative flex items-start gap-1', dragFrom === index && 'opacity-40']}
			onkeydown={(event) => onkeydown(event, index)}
			ondragover={(event) => ondragover(event, index)}
			{ondrop}
		>
			{#if dropAt?.index === index}
				<span
					aria-hidden="true"
					data-drop-indicator={dropAt.after ? 'after' : 'before'}
					class={[
						'pointer-events-none absolute inset-x-0 h-0.5 rounded-full bg-accent',
						dropAt.after ? '-bottom-1.5' : '-top-1.5'
					]}
				></span>
			{/if}
			<span class="cursor-grab text-fg-muted">
				<IconButton
					label="Move {noun} {index + 1} of {items.length}"
					icon="drag"
					size="sm"
					{disabled}
					draggable={!disabled}
					ondragstart={(event) => ondragstart(event, index)}
					ondragend={reset}
				/>
			</span>
			<div class="min-w-0 flex-1">{@render row(entry, index)}</div>
		</li>
	{/each}
</ul>
<p class="sr-only" aria-live="polite">{announcement}</p>
