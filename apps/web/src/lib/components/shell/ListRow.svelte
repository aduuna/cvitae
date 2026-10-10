<script lang="ts">
	import type { Snippet } from 'svelte';
	import Menu, { type MenuItem } from '#lib/components/ui/Menu.svelte';

	interface Props {
		/** Resolved route of the item. */
		href: string;
		title: string;
		/** Secondary details, right of the title. */
		meta?: Snippet;
		menu: MenuItem[];
		menuLabel: string;
	}

	let { href, title, meta, menu, menuLabel }: Props = $props();
</script>

<li
	class="flex h-12 items-center gap-3 border-b border-line pr-2 pl-5 transition-colors duration-120 ease-out last:border-b-0 hover:bg-subtle"
>
	<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- callers pass resolved routes -->
	<a {href} class="min-w-0 flex-1 truncate text-base font-medium text-fg hover:underline">{title}</a
	>
	{#if meta}
		<div class="flex shrink-0 items-center gap-3 text-sm text-fg-muted tabular-nums">
			{@render meta()}
		</div>
	{/if}
	<Menu label={menuLabel} items={menu} />
</li>
