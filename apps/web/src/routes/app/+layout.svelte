<script lang="ts">
	import SideNav from '#lib/components/shell/SideNav.svelte';
	import Toast from '#lib/components/ui/Toast.svelte';

	let { children } = $props();
</script>

<a
	href="#main"
	class="sr-only rounded-md bg-surface px-3 py-2 text-base text-fg shadow-pop focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50"
>
	Skip to content
</a>

<div class="flex h-dvh overflow-hidden bg-canvas text-fg">
	<SideNav />
	<div class="flex min-w-0 flex-1 flex-col">
		{@render children()}
	</div>
</div>

<Toast />
