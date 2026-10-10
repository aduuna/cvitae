<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<kbd
	class="inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-line bg-surface px-1 font-mono text-xs text-fg-muted"
>
	{@render children()}
</kbd>
