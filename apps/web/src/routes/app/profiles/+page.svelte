<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import { canUpgrade, limitReached } from '#lib/billing/plans.ts';
	import LimitNotice from '#lib/components/billing/LimitNotice.svelte';
	import Page from '#lib/components/shell/Page.svelte';
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import EmptyState from '#lib/components/ui/EmptyState.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import Menu from '#lib/components/ui/Menu.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import type { ProfileSummary } from '#lib/cv/types.ts';
	import { formatRelative } from '#lib/format.ts';

	let profiles = $state<ProfileSummary[] | null>(null);
	let loadError = $state<string | null>(null);
	let deleting = $state<ProfileSummary | null>(null);
	let confirmOpen = $state(false);

	/** Set when the plan's profile limit is reached. */
	const blocked = $derived(limitReached(session.usage?.profiles));

	function refreshUsage() {
		session.refreshUsage().catch(() => {});
	}

	async function load() {
		try {
			profiles = await unwrap(api.GET('/api/v1/profiles'));
			loadError = null;
		} catch (error) {
			loadError = errorMessage(error);
		}
	}

	onMount(() => {
		void load();
		refreshUsage();
	});

	/** New profiles start on one page: import a CV (the default) or start from scratch. */
	function create() {
		void goto(resolve('/app/profiles/new'));
	}

	async function run(action: () => Promise<unknown>, done: string) {
		try {
			await action();
			toast.info(done);
			refreshUsage();
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
				disabled: blocked !== null,
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
		<Button variant="primary" icon="new" disabled={blocked !== null} onclick={create}
			>New profile</Button
		>
	{/snippet}

	{#if blocked && profiles !== null}
		<LimitNotice message={blocked} upgrade={canUpgrade(session.usage, session.billingEnabled)} />
	{/if}

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
				hint="A profile holds your roles, skills and education. Import a CV to start one, or fill it in yourself."
				actionLabel="New profile"
				actionIcon="new"
				onaction={create}
			/>
		</Card>
	{:else}
		<ul aria-label="Profiles" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each profiles as profile (profile.id)}
				<!-- The link covers the tile; the menu comes after it in the DOM, so it stays on top. -->
				<li
					class="relative flex min-h-36 flex-col gap-3 rounded-lg border border-line bg-surface p-4 transition-colors duration-120 ease-out hover:border-line-strong"
				>
					<div class="flex items-center gap-2">
						<span class="flex size-9 items-center justify-center rounded-md bg-muted text-fg-muted">
							<Icon name="profiles" />
						</span>
						{#if profile.is_default}<Badge>Default</Badge>{/if}
					</div>
					<a
						href={resolve('/app/profiles/[id]', { id: profile.id })}
						class="line-clamp-2 pr-8 text-base font-semibold text-fg after:absolute after:inset-0 after:rounded-lg focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-accent"
					>
						{profile.name}
					</a>
					<p class="mt-auto text-sm text-fg-muted">Edited {formatRelative(profile.updated_at)}</p>
					<div class="absolute top-3 right-3">
						<Menu label="Actions for {profile.name}" items={menu(profile)} />
					</div>
				</li>
			{/each}
		</ul>
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
