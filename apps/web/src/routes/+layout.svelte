<script lang="ts">
	import '../app.css';
	import Toast from '#lib/components/ui/Toast.svelte';
	import { theme } from '#lib/theme.svelte.ts';

	let { children } = $props();

	$effect(() => {
		document.documentElement.dataset.theme = theme.resolved;
	});
</script>

{@render children()}

<!-- Here, not in the app shell, so a toast survives the page that raised it (account deleted). -->
<Toast />
