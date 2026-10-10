<script lang="ts" module>
	export const badgeVariants = {
		neutral: 'bg-muted text-fg',
		outline: 'border border-line text-fg-muted'
	} as const;
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		variant?: keyof typeof badgeVariants;
		children: Snippet;
	}

	let { variant = 'neutral', children }: Props = $props();
</script>

<span
	data-variant={variant}
	class={[
		'inline-flex h-5 items-center rounded-sm px-1.5 text-xs font-medium whitespace-nowrap',
		badgeVariants[variant]
	]}
>
	{@render children()}
</span>
