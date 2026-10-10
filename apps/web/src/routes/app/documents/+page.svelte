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
	import Dialog from '#lib/components/ui/Dialog.svelte';
	import EmptyState from '#lib/components/ui/EmptyState.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import Select from '#lib/components/ui/Select.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import { exportPdf } from '#lib/cv/export.ts';
	import type { DocumentSummary, ProfileSummary } from '#lib/cv/types.ts';
	import { formatPages, formatRelative } from '#lib/format.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import { DEFAULT_TEMPLATE_ID, templates } from '#lib/templates.svelte.ts';

	let documents = $state<DocumentSummary[] | null>(null);
	let profiles = $state<ProfileSummary[]>([]);
	let loadError = $state<string | null>(null);

	let newOpen = $state(false);
	let newProfileId = $state('');
	let newName = $state('');
	let newTemplateId = $state(DEFAULT_TEMPLATE_ID);
	let creating = $state(false);

	let renaming = $state<DocumentSummary | null>(null);
	let renameOpen = $state(false);
	let renameValue = $state('');
	let renameSaving = $state(false);

	let deleting = $state<DocumentSummary | null>(null);
	let deleteOpen = $state(false);

	const selectedProfile = $derived(profiles.find((profile) => profile.id === newProfileId));

	async function load() {
		try {
			const [docs, profileList] = await Promise.all([
				unwrap(api.GET('/api/v1/documents')),
				unwrap(api.GET('/api/v1/profiles'))
			]);
			documents = docs;
			profiles = profileList;
			loadError = null;
		} catch (error) {
			loadError = errorMessage(error);
		}
	}

	onMount(() => {
		void load();
		templates.load().catch(() => toast.error('Templates could not load. Reload to try again.'));
	});

	function openNew() {
		newProfileId = (profiles.find((profile) => profile.is_default) ?? profiles[0])?.id ?? '';
		newName = '';
		newTemplateId = session.me?.default_template_id ?? DEFAULT_TEMPLATE_ID;
		newOpen = true;
	}

	async function createDocument(event?: SubmitEvent) {
		event?.preventDefault();
		if (!newProfileId) return;
		creating = true;
		try {
			const doc = await unwrap(
				api.POST('/api/v1/documents', {
					body: {
						profile_id: newProfileId,
						name: newName.trim() || undefined,
						template_id: newTemplateId
					}
				})
			);
			newOpen = false;
			await goto(resolve('/app/documents/[id]', { id: doc.id }));
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			creating = false;
		}
	}

	async function createProfile() {
		try {
			const profile = await unwrap(api.POST('/api/v1/profiles', { body: {} }));
			await goto(resolve('/app/profiles/[id]', { id: profile.id }));
		} catch (error) {
			toast.error(errorMessage(error));
		}
	}

	async function rename(event?: SubmitEvent) {
		event?.preventDefault();
		const target = renaming;
		if (!target || !renameValue.trim()) return;
		renameSaving = true;
		try {
			await unwrap(
				api.PATCH('/api/v1/documents/{document_id}', {
					params: { path: { document_id: target.id } },
					body: { name: renameValue.trim() }
				})
			);
			renameOpen = false;
			await load();
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			renameSaving = false;
		}
	}

	async function duplicate(doc: DocumentSummary) {
		try {
			await unwrap(
				api.POST('/api/v1/documents/{document_id}/duplicate', {
					params: { path: { document_id: doc.id } }
				})
			);
			toast.info(`Duplicated ${doc.name}.`);
			await load();
		} catch (error) {
			toast.error(errorMessage(error));
		}
	}

	async function download(doc: DocumentSummary) {
		try {
			const result = await exportPdf(doc.id);
			if (!result.ok) {
				toast.error(
					`${doc.name} still has placeholders. Open it to fill them in, or use Export anyway in the editor.`
				);
			}
		} catch (error) {
			toast.error(errorMessage(error));
		}
	}

	async function remove() {
		const target = deleting;
		if (!target) return;
		try {
			await unwrap(
				api.DELETE('/api/v1/documents/{document_id}', {
					params: { path: { document_id: target.id } }
				})
			);
			toast.info(`Deleted ${target.name}.`);
			await load();
		} catch (error) {
			toast.error(errorMessage(error));
		}
	}

	function menu(doc: DocumentSummary) {
		return [
			{
				label: 'Rename',
				onselect: () => {
					renaming = doc;
					renameValue = doc.name;
					renameOpen = true;
				}
			},
			{ label: 'Duplicate', icon: 'duplicate' as const, onselect: () => duplicate(doc) },
			{ label: 'Download PDF', icon: 'download' as const, onselect: () => download(doc) },
			{
				label: 'Delete',
				icon: 'delete' as const,
				danger: true,
				onselect: () => {
					deleting = doc;
					deleteOpen = true;
				}
			}
		];
	}
</script>

<Page title="Documents">
	{#snippet actions()}
		<Button variant="primary" icon="new" disabled={documents === null} onclick={openNew}
			>New CV</Button
		>
	{/snippet}

	{#if loadError}
		<Card>
			<p role="alert" class="text-base text-danger">{loadError}</p>
			<div class="mt-3"><Button onclick={load}>Try again</Button></div>
		</Card>
	{:else if documents === null}
		<Card><Skeleton lines={3} /></Card>
	{:else if documents.length === 0 && profiles.length === 0}
		<Card padding="none">
			<EmptyState
				icon="profiles"
				title="Start with a profile"
				hint="Add your experience once, then make a CV for each job."
				actionLabel="New profile"
				actionIcon="new"
				onaction={createProfile}
			/>
		</Card>
	{:else if documents.length === 0}
		<Card padding="none">
			<EmptyState
				icon="documents"
				title="No CVs yet"
				hint="Make a CV from one of your profiles."
				actionLabel="New CV"
				actionIcon="new"
				onaction={openNew}
			/>
		</Card>
	{:else}
		<Card padding="none">
			<ul aria-label="CVs">
				{#each documents as doc (doc.id)}
					<ListRow
						href={resolve('/app/documents/[id]', { id: doc.id })}
						title={doc.name}
						menu={menu(doc)}
						menuLabel="Actions for {doc.name}"
					>
						{#snippet meta()}
							<Badge variant="outline">{templates.name(doc.template_id)}</Badge>
							{#if doc.page_count}<span>{formatPages(doc.page_count)}</span>{/if}
							<span>Edited {formatRelative(doc.updated_at)}</span>
						{/snippet}
					</ListRow>
				{/each}
			</ul>
		</Card>
	{/if}
</Page>

<Dialog bind:open={newOpen} title="New CV" size="md">
	{#if profiles.length === 0}
		<p>A CV is made from a profile. Create a profile first.</p>
	{:else}
		<form id="new-cv" class="flex flex-col gap-4" onsubmit={createDocument}>
			<Select
				label="Profile"
				bind:value={newProfileId}
				options={profiles.map((profile) => ({ value: profile.id, label: profile.name }))}
				help="The CV starts as a copy. Later profile edits do not change it."
			/>
			<Input
				label="Name"
				bind:value={newName}
				placeholder={selectedProfile ? `${selectedProfile.name} CV` : 'CV'}
			/>
			<Select
				label="Template"
				bind:value={newTemplateId}
				options={templates.list.map((template) => ({ value: template.id, label: template.name }))}
			/>
		</form>
	{/if}
	{#snippet footer()}
		<Button onclick={() => (newOpen = false)}>Cancel</Button>
		{#if profiles.length === 0}
			<Button variant="primary" icon="new" onclick={createProfile}>New profile</Button>
		{:else}
			<Button variant="primary" type="submit" form="new-cv" loading={creating}>Create CV</Button>
		{/if}
	{/snippet}
</Dialog>

<Dialog bind:open={renameOpen} title="Rename CV">
	<form id="rename-cv" onsubmit={rename}>
		<Input
			label="Name"
			bind:value={renameValue}
			error={renameValue.trim() ? undefined : 'Give the CV a name.'}
		/>
	</form>
	{#snippet footer()}
		<Button onclick={() => (renameOpen = false)}>Cancel</Button>
		<Button
			variant="primary"
			type="submit"
			form="rename-cv"
			loading={renameSaving}
			disabled={!renameValue.trim()}
		>
			Rename CV
		</Button>
	{/snippet}
</Dialog>

<ConfirmDialog
	bind:open={deleteOpen}
	title="Delete CV"
	message="{deleting?.name ?? 'This CV'} and its version history will be deleted."
	confirmLabel="Delete CV"
	danger
	onconfirm={remove}
/>
