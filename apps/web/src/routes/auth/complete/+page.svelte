<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { errorMessage } from '#lib/api/client.ts';
	import { pendingEmail, session } from '#lib/auth/session.svelte.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import Logo from '#lib/components/shell/Logo.svelte';

	// Opened from the email link. The email it was sent to is remembered in this browser; on
	// another device the user confirms it.
	let email = $state('');
	let needsEmail = $state(false);
	let busy = $state(false);
	let error = $state<string | null>(null);
	let invalidLink = $state(false);

	async function complete(address: string) {
		busy = true;
		error = null;
		try {
			await session.completeEmailLink(address, location.href);
			await goto(resolve('/app/documents'), { replaceState: true });
		} catch (failure) {
			error = errorMessage(failure);
			needsEmail = true;
		} finally {
			busy = false;
		}
	}

	onMount(() => {
		if (!session.isEmailLink(location.href)) {
			invalidLink = true;
			return;
		}
		const remembered = pendingEmail.get();
		if (remembered) void complete(remembered);
		else needsEmail = true;
	});

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (email.trim()) void complete(email.trim());
	}
</script>

<svelte:head>
	<title>Signing in - Chameleon vitae</title>
</svelte:head>

<main
	class="flex min-h-dvh flex-col items-center justify-center gap-6 bg-canvas px-4 py-12 text-fg"
>
	<Logo size="lg" label="Chameleon vitae" />
	<section
		class="flex w-full max-w-100 flex-col gap-4 rounded-lg border border-line bg-surface p-5"
		aria-live="polite"
	>
		{#if invalidLink}
			<h1 class="text-lg font-semibold">This link cannot sign you in</h1>
			<p class="text-base text-fg-muted">Request a new sign-in link and open it in this browser.</p>
			<Button variant="primary" onclick={() => goto(resolve('/login'))}>Back to sign in</Button>
		{:else if needsEmail}
			<h1 class="text-lg font-semibold">Confirm your email</h1>
			<p class="text-base text-fg-muted">Enter the email address the sign-in link was sent to.</p>
			<form class="flex flex-col gap-3" onsubmit={submit}>
				<Input label="Email" type="email" autocomplete="email" required bind:value={email} />
				<Button type="submit" variant="primary" loading={busy}>Sign in</Button>
			</form>
		{:else}
			<h1 class="text-lg font-semibold">Signing you in</h1>
		{/if}
		{#if error}
			<p class="text-sm text-danger" role="alert">{error}</p>
		{/if}
	</section>
</main>
