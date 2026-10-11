<script lang="ts">
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<!-- A gap the user must fill, in the same yellow the CV preview uses. -->
<span class="rounded-sm bg-placeholder px-1 text-placeholder-fg">{@render children()}</span>
