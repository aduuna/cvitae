<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { errorMessage } from '#lib/api/client.ts';
	import { afterSignIn, nextPath, withNext } from '#lib/auth/next.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import Logo from '#lib/components/shell/Logo.svelte';
	import { asset } from '$app/paths';

	// /login?password: a password form in place of the email link, for accounts made with one (the
	// store review account). Not linked anywhere, and it creates no accounts.
	const withPassword = new URL(location.href).searchParams.has('password');

	let email = $state('');
	let password = $state('');
	let sentTo = $state<string | null>(null);
	let busy = $state<'google' | 'email' | 'password' | null>(null);
	let error = $state<string | null>(null);

	// Back to the app page the user was sent here from (?next=), else Documents.
	$effect(() => {
		if (session.status === 'signed-in') {
			// eslint-disable-next-line svelte/no-navigation-without-resolve -- an app path checked by afterSignIn
			void goto(afterSignIn(new URL(location.href)), { replaceState: true });
		}
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
			const complete = `${location.origin}${resolve('/auth/complete')}`;
			await session.sendEmailLink(address, withNext(complete, nextPath(new URL(location.href))));
			sentTo = address;
		} catch (failure) {
			error = errorMessage(failure);
		} finally {
			busy = null;
		}
	}

	async function signInWithPassword(event: SubmitEvent) {
		event.preventDefault();
		const address = email.trim();
		if (!address || !password) return;
		busy = 'password';
		error = null;
		try {
			await session.signInWithPassword(address, password);
		} catch (failure) {
			error = errorMessage(failure);
		} finally {
			busy = null;
		}
	}
</script>

<svelte:head>
	<title>Sign in - Chameleon vitae</title>
</svelte:head>

<main class="flex min-h-dvh items-center justify-center bg-canvas px-4 py-12 text-fg">
	{#if session.status === 'signed-out'}
		<div class="flex w-full max-w-100 flex-col gap-6">
			<div class="flex flex-col gap-2">
				<a href={resolve('/')} class="self-start rounded-md">
					<Logo size="lg" label="Chameleon vitae home" />
				</a>
				<h1 class="text-2xl font-semibold">Chameleon vitae</h1>
				<p class="text-base text-fg-muted">
					Paste a job description and get a CV tailored to it, built from what you already wrote.
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
					<div class="flex flex-col gap-1">
						<h2 class="text-lg font-semibold">Sign in</h2>
						<p class="text-sm text-fg-muted">
							{withPassword
								? 'Use the email and password you were given.'
								: 'New here? Your first sign-in creates your account.'}
						</p>
					</div>
					<Button
						variant="secondary"
						size="lg"
						loading={busy === 'google'}
						disabled={busy !== null}
						onclick={google}
					>
						<!-- Google's mark, in its own colours as Google's sign-in branding requires. -->
						<img src={asset('brand/google-g.svg')} alt="" class="size-4" />
						Continue with Google
					</Button>
					<div class="flex items-center gap-3 text-sm text-fg-muted" aria-hidden="true">
						<span class="h-px flex-1 bg-line"></span>
						or
						<span class="h-px flex-1 bg-line"></span>
					</div>
					{#if withPassword}
						<form class="flex flex-col gap-3" onsubmit={signInWithPassword}>
							<Input
								label="Email"
								type="email"
								autocomplete="username"
								required
								bind:value={email}
							/>
							<Input
								label="Password"
								type="password"
								autocomplete="current-password"
								required
								bind:value={password}
							/>
							<Button
								type="submit"
								variant="primary"
								size="lg"
								loading={busy === 'password'}
								disabled={busy !== null}
							>
								Sign in
							</Button>
						</form>
					{:else}
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
				{/if}
				{#if error}
					<p class="text-sm text-danger" role="alert">{error}</p>
				{/if}
			</section>
			<p class="text-sm text-fg-muted">
				By signing in you agree to how we handle your data, set out in our <a
					href={resolve('/privacy')}
					class="text-fg underline underline-offset-4">privacy policy</a
				>.
			</p>
		</div>
	{/if}
</main>
