<script lang="ts">
	import { untrack } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { Autosave } from '#lib/autosave.svelte.ts';
	import CvEditor from '#lib/components/cv/CvEditor.svelte';
	import SaveStatus from '#lib/components/cv/SaveStatus.svelte';
	import Page from '#lib/components/shell/Page.svelte';
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import type { CvContent, Profile } from '#lib/cv/types.ts';

	interface Draft {
		name: string;
		content: CvContent;
	}

	const id = $derived(page.params.id ?? '');

	let profile = $state<Profile | null>(null);
	let loadError = $state<string | null>(null);
	let autosave = $state<Autosave<Draft> | null>(null);
	let makingDefault = $state(false);

	async function load(profileId: string) {
		profile = null;
		loadError = null;
		try {
			const loaded = await unwrap(
				api.GET('/api/v1/profiles/{profile_id}', { params: { path: { profile_id: profileId } } })
			);
			autosave?.dispose();
			autosave = new Autosave<Draft>(
				(draft) => save(profileId, draft),
				{ name: loaded.name, content: loaded.content },
				600
			);
			profile = loaded;
		} catch (error) {
			loadError = errorMessage(error);
		}
	}

	async function save(profileId: string, draft: Draft) {
		const updated = await unwrap(
			api.PATCH('/api/v1/profiles/{profile_id}', {
				params: { path: { profile_id: profileId } },
				body: { name: draft.name.trim() || undefined, content: draft.content }
			})
		);
		if (profile?.id === profileId) profile.updated_at = updated.updated_at;
	}

	$effect(() => {
		void load(id);
	});

	$effect(() => {
		if (!profile || !autosave) return;
		const draft = { name: profile.name, content: $state.snapshot(profile.content) };
		const saver = autosave;
		untrack(() => saver.schedule(draft));
	});

	$effect(() => () => autosave?.dispose());

	beforeNavigate(() => {
		if (autosave?.dirty) void autosave.flush();
	});

	function onbeforeunload(event: BeforeUnloadEvent) {
		if (autosave?.dirty) event.preventDefault();
	}

	async function makeDefault() {
		if (!profile) return;
		makingDefault = true;
		try {
			const updated = await unwrap(
				api.PATCH('/api/v1/profiles/{profile_id}', {
					params: { path: { profile_id: profile.id } },
					body: { is_default: true }
				})
			);
			profile.is_default = updated.is_default;
			toast.info(`${profile.name} is now your default profile.`);
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			makingDefault = false;
		}
	}
</script>

<svelte:window {onbeforeunload} />

<Page title={profile?.name || 'Profile'}>
	{#snippet actions()}
		{#if autosave}<SaveStatus {autosave} />{/if}
	{/snippet}

	{#if loadError}
		<Card>
			<p role="alert" class="text-base text-danger">{loadError}</p>
			<div class="mt-3"><Button onclick={() => load(id)}>Try again</Button></div>
		</Card>
	{:else if profile === null}
		<Card><Skeleton lines={4} /></Card>
	{:else}
		<Card title="Profile">
			<div class="flex flex-col gap-3">
				<Input
					label="Profile name"
					bind:value={profile.name}
					help="Only you see this, for example Data engineering or Backend."
					error={profile.name.trim() ? undefined : 'Give the profile a name.'}
				/>
				<div class="flex items-center gap-3">
					{#if profile.is_default}
						<Badge>Default profile</Badge>
						<span class="text-sm text-fg-muted">New CVs start from this profile.</span>
					{:else}
						<Button size="sm" loading={makingDefault} onclick={makeDefault}>Make default</Button>
					{/if}
				</div>
			</div>
		</Card>
		<CvEditor bind:content={profile.content} />
	{/if}
</Page>
