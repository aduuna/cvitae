<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		/** Page title, shown in the top bar and the browser tab. One per page. */
		title: string;
		/** `narrow` centres a 960px column (list and form pages); `full` is for the editor. */
		width?: 'narrow' | 'full';
		/** Top bar actions, right-aligned; the primary action goes last. */
		actions?: Snippet;
		children?: Snippet;
	}

	let { title, width = 'narrow', actions, children }: Props = $props();
</script>

<svelte:head>
	<title>{title} - Chameleon vitae</title>
</svelte:head>

<header
	class="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-line bg-surface px-6"
>
	<h1 class="truncate text-xl font-semibold text-fg">{title}</h1>
	{#if actions}
		<div class="flex shrink-0 items-center gap-2">{@render actions()}</div>
	{/if}
</header>

<!-- relative: absolute children (sr-only text) stay inside this scroller instead of stretching the window. -->
<main id="main" tabindex="-1" class="relative min-h-0 flex-1 overflow-y-auto focus:outline-none">
	{#if width === 'narrow'}
		<div class="mx-auto flex w-full max-w-240 flex-col gap-6 px-6 py-6">
			{@render children?.()}
		</div>
	{:else}
		{@render children?.()}
	{/if}
</main>
