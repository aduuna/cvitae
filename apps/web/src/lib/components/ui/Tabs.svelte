<script lang="ts" module>
	export interface TabItem {
		id: string;
		label: string;
	}
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	import { nextIndex } from './roving';

	interface Props {
		tabs: TabItem[];
		/** Id of the active tab. */
		value: string;
		/** Accessible name of the tab list. */
		label: string;
		/** Renders the panel content for the active tab id. */
		panel: Snippet<[string]>;
	}

	let { tabs, value = $bindable(), label, panel }: Props = $props();

	const baseId = $props.id();
	let buttons: HTMLButtonElement[] = $state([]);

	function onkeydown(event: KeyboardEvent, index: number) {
		if (event.key === 'ArrowUp' || event.key === 'ArrowDown') return;
		const next = nextIndex(event.key, index, tabs.length);
		const tab = next === null ? undefined : tabs[next];
		if (next === null || !tab) return;
		event.preventDefault();
		value = tab.id;
		buttons[next]?.focus();
	}
</script>

<div class="flex flex-col">
	<div role="tablist" aria-label={label} class="flex gap-4 border-b border-line">
		{#each tabs as tab, index (tab.id)}
			{@const selected = tab.id === value}
			<button
				bind:this={buttons[index]}
				id="{baseId}-tab-{tab.id}"
				type="button"
				role="tab"
				aria-selected={selected}
				aria-controls="{baseId}-panel"
				tabindex={selected ? 0 : -1}
				onclick={() => (value = tab.id)}
				onkeydown={(event) => onkeydown(event, index)}
				class={[
					'-mb-px h-9 border-b-2 text-base transition-colors duration-120 ease-out',
					selected
						? 'border-accent font-medium text-fg'
						: 'border-transparent text-fg-muted hover:text-fg'
				]}
			>
				{tab.label}
			</button>
		{/each}
	</div>
	<div
		id="{baseId}-panel"
		role="tabpanel"
		aria-labelledby="{baseId}-tab-{value}"
		tabindex="0"
		class="pt-4"
	>
		{@render panel(value)}
	</div>
</div>
