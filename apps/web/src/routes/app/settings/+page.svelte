<script lang="ts">
	import { onMount } from 'svelte';
	import { errorMessage } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import Page from '#lib/components/shell/Page.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';

	let name = $state('');
	let loaded = $state(false);
	let saving = $state(false);
	let signingOut = $state(false);

	const unchanged = $derived((session.me?.display_name ?? '') === name.trim());

	onMount(async () => {
		try {
			const me = await session.loadMe();
			name = me.display_name ?? '';
			loaded = true;
		} catch (error) {
			toast.error(errorMessage(error));
		}
	});

	async function saveName(event: SubmitEvent) {
		event.preventDefault();
		saving = true;
		try {
			await session.updateMe({ display_name: name.trim() });
			toast.info('Name saved.');
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			saving = false;
		}
	}

	async function signOut() {
		signingOut = true;
		try {
			await session.signOut();
		} catch (error) {
			toast.error(errorMessage(error));
			signingOut = false;
		}
	}
</script>

<Page title="Settings">
	<Card title="Account">
		{#if loaded}
			<div class="flex flex-col gap-4">
				<form class="flex items-end gap-2" onsubmit={saveName}>
					<div class="flex-1">
						<Input label="Name" autocomplete="name" maxlength={200} bind:value={name} />
					</div>
					<Button type="submit" loading={saving} disabled={unchanged}>Save name</Button>
				</form>
				<Input
					label="Email"
					value={session.me?.email ?? ''}
					readonly
					help="The address you sign in with."
				/>
				<div>
					<Button icon="sign-out" loading={signingOut} onclick={signOut}>Sign out</Button>
				</div>
			</div>
		{:else}
			<Skeleton lines={3} />
		{/if}
	</Card>
</Page>
