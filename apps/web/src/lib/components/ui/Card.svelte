<script lang="ts" module>
	export const cardPadding = {
		none: '',
		md: 'p-5'
	} as const;
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		/** Section heading inside the card (form pages). */
		title?: string;
		/** `none` for cards that hold full-width rows (list pages). */
		padding?: keyof typeof cardPadding;
		children: Snippet;
	}

	let { title, padding = 'md', children }: Props = $props();
</script>

<section class={['rounded-lg border border-line bg-surface', cardPadding[padding]]}>
	{#if title}
		<h2 class={['text-lg font-semibold text-fg', padding === 'none' ? 'px-5 pt-5 pb-3' : 'mb-4']}>
			{title}
		</h2>
	{/if}
	{@render children()}
</section>
