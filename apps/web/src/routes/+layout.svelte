<script lang="ts">
	import '../app.css';
	import { theme } from '#lib/theme.svelte.ts';

	let { children } = $props();

	$effect(() => {
		document.documentElement.dataset.theme = theme.resolved;
	});
</script>

{@render children()}
