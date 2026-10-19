<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { browserLabel, findExtension, handOver, type Found } from '#lib/extension/connect.ts';

	// Connects the extension in this browser: makes a connection and hands its token to the
	// extension's content script on this page. The token is never shown or kept here.
	type Phase = 'looking' | 'missing' | 'ready' | 'connecting' | 'connected' | 'failed';

	interface Props {
		/** After a connection was made, so the page can list it. */
		onconnected?: () => void;
	}

	let { onconnected }: Props = $props();

	let phase = $state<Phase>('looking');
	let found = $state<Found | null>(null);
	let error = $state<string | null>(null);

	const email = $derived(session.email ?? '');

	async function look() {
		phase = 'looking';
		found = await findExtension();
		phase = found ? 'ready' : 'missing';
	}

	onMount(look);

	async function connect() {
		phase = 'connecting';
		error = null;
		let connectionId: string | null = null;
		try {
			const created = await unwrap(
				api.POST('/api/v1/extension/connections', {
					body: { label: browserLabel(navigator.userAgent) }
				})
			);
			connectionId = created.id;
			const result = await handOver(created.token, email);
			if (result.ok) {
				phase = 'connected';
				onconnected?.();
				return;
			}
			error = result.message;
		} catch (failure) {
			error = errorMessage(failure);
		}
		phase = 'failed';
		// The extension never got the token, or refused it: leave no unused connection behind.
		if (connectionId) {
			await unwrap(
				api.DELETE('/api/v1/extension/connections/{connection_id}', {
					params: { path: { connection_id: connectionId } }
				})
			).catch(() => {});
		}
	}
</script>

<Card title="This browser">
	<div class="flex flex-col gap-4" aria-live="polite">
		{#if phase === 'looking'}
			<Skeleton lines={2} />
		{:else if phase === 'missing'}
			<p class="text-base text-fg">The extension is not installed in this browser, or it is off.</p>
			<p class="text-sm text-fg-muted">
				Install it, or turn it on in the browser's extension settings, then try again.
			</p>
			<div>
				<Button onclick={look}>Try again</Button>
			</div>
		{:else if phase === 'connected'}
			<p class="flex items-center gap-2 text-base text-fg">
				<Icon name="check" />
				Connected to {email}.
			</p>
			<p class="text-sm text-fg-muted">
				On a job application, open the extension from the toolbar and choose Fill form.
			</p>
		{:else}
			<p class="text-base text-fg">
				Connect the extension in this browser to <span class="font-medium">{email}</span>.
			</p>
			{#if found?.connectedAs === email}
				<p class="text-sm text-fg">This browser is connected to {email} already.</p>
			{:else if found?.connectedAs}
				<p class="text-sm text-fg">
					This browser is connected to {found.connectedAs}. Connecting switches it to {email}.
				</p>
			{/if}
			{#if error}
				<p class="text-sm text-danger" role="alert">{error}</p>
			{/if}
			<div>
				<Button
					variant="primary"
					icon="extension"
					loading={phase === 'connecting'}
					onclick={connect}
				>
					{found?.connectedAs === email ? 'Connect again' : 'Connect extension'}
				</Button>
			</div>
		{/if}
	</div>
</Card>
