<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { errorMessage } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Input from '#lib/components/ui/Input.svelte';

	let email = $state('');
	let sentTo = $state<string | null>(null);
	let busy = $state<'google' | 'email' | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		if (session.status === 'signed-in')
			void goto(resolve('/app/documents'), { replaceState: true });
	});

	async function google() {
		busy = 'google';
		error = null;
		try {
			await session.signInWithGoogle();
		} catch (failure) {
			error = errorMessage(failure);
		} finally {
			busy = null;
		}
	}

	async function sendLink(event: SubmitEvent) {
		event.preventDefault();
		const address = email.trim();
		if (!address) return;
		busy = 'email';
		error = null;
		try {
			await session.sendEmailLink(address, `${location.origin}${resolve('/auth/complete')}`);
			sentTo = address;
		} catch (failure) {
			error = errorMessage(failure);
		} finally {
			busy = null;
		}
	}
</script>

<svelte:head>
	<title>Chameleon vitae</title>
</svelte:head>

<main class="flex min-h-dvh items-center justify-center bg-canvas px-4 py-12 text-fg">
	{#if session.status === 'signed-out'}
		<div class="flex w-full max-w-100 flex-col gap-6">
			<div class="flex flex-col gap-2">
				<h1 class="text-2xl font-semibold">Chameleon vitae</h1>
				<p class="text-base text-fg-muted">
					Paste a job description and get a CV tailored to it, typeset properly, without the AI
					inventing anything.
				</p>
			</div>

			<section class="flex flex-col gap-4 rounded-lg border border-line bg-surface p-5">
				{#if sentTo}
					<div class="flex flex-col gap-2" aria-live="polite">
						<h2 class="text-lg font-semibold">Check your email</h2>
						<p class="text-base text-fg-muted">
							We sent a sign-in link to <span class="font-medium text-fg">{sentTo}</span>. Open it
							in this browser to finish signing in.
						</p>
					</div>
					<Button variant="ghost" onclick={() => (sentTo = null)}>Use a different email</Button>
				{:else}
					<h2 class="text-lg font-semibold">Sign in</h2>
					<Button
						variant="secondary"
						size="lg"
						loading={busy === 'google'}
						disabled={busy !== null}
						onclick={google}
					>
						Continue with Google
					</Button>
					<div class="flex items-center gap-3 text-sm text-fg-muted" aria-hidden="true">
						<span class="h-px flex-1 bg-line"></span>
						or
						<span class="h-px flex-1 bg-line"></span>
					</div>
					<form class="flex flex-col gap-3" onsubmit={sendLink}>
						<Input
							label="Email"
							type="email"
							autocomplete="email"
							required
							bind:value={email}
							help="We email you a link; no password needed."
						/>
						<Button
							type="submit"
							variant="primary"
							size="lg"
							loading={busy === 'email'}
							disabled={busy !== null}
						>
							Email me a sign-in link
						</Button>
					</form>
				{/if}
				{#if error}
					<p class="text-sm text-danger" role="alert">{error}</p>
				{/if}
			</section>
		</div>
	{/if}
</main>
