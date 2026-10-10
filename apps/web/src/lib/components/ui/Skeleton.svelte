<script lang="ts" module>
	export const skeletonHeights = {
		sm: 'h-16',
		md: 'h-32',
		lg: 'h-64'
	} as const;
</script>

<script lang="ts">
	interface Props {
		variant?: 'lines' | 'block';
		/** Number of text lines (lines variant). The last line is shorter. */
		lines?: number;
		/** Block height (block variant). */
		height?: keyof typeof skeletonHeights;
	}

	let { variant = 'lines', lines = 3, height = 'md' }: Props = $props();
</script>

<div role="status" class="w-full">
	<span class="sr-only">Loading</span>
	{#if variant === 'block'}
		<div
			aria-hidden="true"
			data-skeleton="block"
			class={['w-full animate-pulse rounded-md bg-muted', skeletonHeights[height]]}
		></div>
	{:else}
		<div aria-hidden="true" class="flex flex-col gap-2">
			{#each { length: lines }, index (index)}
				<div
					data-skeleton="line"
					class={[
						'h-3 animate-pulse rounded-sm bg-muted',
						index === lines - 1 && lines > 1 ? 'w-2/3' : 'w-full'
					]}
				></div>
			{/each}
		</div>
	{/if}
</div>
