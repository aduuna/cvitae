<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { signInPath } from '#lib/auth/next.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import SideNav from '#lib/components/shell/SideNav.svelte';
	import Toast from '#lib/components/ui/Toast.svelte';

	let { children } = $props();

	// Anyone who signs out goes to the home page. A visitor who arrives signed out goes to sign in,
	// and comes back to this page afterwards (the extension's connect page, for one).
	let signedIn = false;
	$effect(() => {
		if (session.status === 'signed-in') signedIn = true;
		if (session.status !== 'signed-out') return;
		if (signedIn) void goto(resolve('/'), { replaceState: true });
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- sign-in with ?next=, from signInPath
		else void goto(signInPath(page.url), { replaceState: true });
	});
</script>

{#if session.status === 'signed-in'}
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
{/if}
