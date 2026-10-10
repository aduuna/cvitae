<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import ListRow from '#lib/components/shell/ListRow.svelte';
	import Page from '#lib/components/shell/Page.svelte';
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import EmptyState from '#lib/components/ui/EmptyState.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import type { ProfileSummary } from '#lib/cv/types.ts';
	import { formatRelative } from '#lib/format.ts';

	let profiles = $state<ProfileSummary[] | null>(null);
	let loadError = $state<string | null>(null);
	let creating = $state(false);
	let deleting = $state<ProfileSummary | null>(null);
	let confirmOpen = $state(false);

	async function load() {
		try {
			profiles = await unwrap(api.GET('/api/v1/profiles'));
			loadError = null;
		} catch (error) {
			loadError = errorMessage(error);
		}
	}

	onMount(load);

	async function create() {
		creating = true;
		try {
			const profile = await unwrap(api.POST('/api/v1/profiles', { body: {} }));
			await goto(resolve('/app/profiles/[id]', { id: profile.id }));
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			creating = false;
		}
	}

	async function run(action: () => Promise<unknown>, done: string) {
		try {
			await action();
			toast.info(done);
			await load();
		} catch (error) {
			toast.error(errorMessage(error));
		}
	}

	function path(profile: ProfileSummary) {
		return { params: { path: { profile_id: profile.id } } };
	}

	function menu(profile: ProfileSummary) {
		return [
			{
				label: 'Duplicate',
				icon: 'duplicate' as const,
				onselect: () =>
					run(
						() => unwrap(api.POST('/api/v1/profiles/{profile_id}/duplicate', path(profile))),
						`Duplicated ${profile.name}.`
					)
			},
			{
				label: 'Make default',
				disabled: profile.is_default,
				onselect: () =>
					run(
						() =>
							unwrap(
								api.PATCH('/api/v1/profiles/{profile_id}', {
									...path(profile),
									body: { is_default: true }
								})
							),
						`${profile.name} is now your default profile.`
					)
			},
			{
				label: 'Delete',
				icon: 'delete' as const,
				danger: true,
				onselect: () => {
					deleting = profile;
					confirmOpen = true;
				}
			}
		];
	}
</script>

<Page title="Profiles">
	{#snippet actions()}
		<Button variant="primary" icon="new" loading={creating} onclick={create}>New profile</Button>
	{/snippet}

	{#if loadError}
		<Card>
			<p role="alert" class="text-base text-danger">{loadError}</p>
			<div class="mt-3"><Button onclick={load}>Try again</Button></div>
		</Card>
	{:else if profiles === null}
		<Card><Skeleton lines={3} /></Card>
	{:else if profiles.length === 0}
		<Card padding="none">
			<EmptyState
				icon="profiles"
				title="No profiles yet"
				hint="A profile holds your roles, skills and education. CVs are made from it."
				actionLabel="New profile"
				actionIcon="new"
				onaction={create}
			/>
		</Card>
	{:else}
		<Card padding="none">
			<ul aria-label="Profiles">
				{#each profiles as profile (profile.id)}
					<ListRow
						href={resolve('/app/profiles/[id]', { id: profile.id })}
						title={profile.name}
						menu={menu(profile)}
						menuLabel="Actions for {profile.name}"
					>
						{#snippet meta()}
							{#if profile.is_default}<Badge>Default</Badge>{/if}
							<span>Edited {formatRelative(profile.updated_at)}</span>
						{/snippet}
					</ListRow>
				{/each}
			</ul>
		</Card>
	{/if}
</Page>

<ConfirmDialog
	bind:open={confirmOpen}
	title="Delete profile"
	message="{deleting?.name ?? 'This profile'} will be deleted. CVs made from it are kept."
	confirmLabel="Delete profile"
	danger
	onconfirm={async () => {
		const target = deleting;
		if (!target) return;
		await run(
			() => unwrap(api.DELETE('/api/v1/profiles/{profile_id}', path(target))),
			`Deleted ${target.name}.`
		);
	}}
/>
