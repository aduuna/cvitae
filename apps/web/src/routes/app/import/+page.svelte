<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { runImport, type ImportSource } from '#lib/ai/imports.ts';
	import { modelLabel, pickModel } from '#lib/ai/models.ts';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import { blockedReason, canUpgrade } from '#lib/billing/plans.ts';
	import LimitNotice from '#lib/components/billing/LimitNotice.svelte';
	import GenerationProgress from '#lib/components/ai/GenerationProgress.svelte';
	import ModelSelect from '#lib/components/ai/ModelSelect.svelte';
	import CvEditor from '#lib/components/cv/CvEditor.svelte';
	import Page from '#lib/components/shell/Page.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import Dropzone from '#lib/components/ui/Dropzone.svelte';
	import Icon from '#lib/components/ui/Icon.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import Tabs from '#lib/components/ui/Tabs.svelte';
	import Textarea from '#lib/components/ui/Textarea.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import type { AiModel, CvContent, UploadSummary } from '#lib/cv/types.ts';
	import { formatBytes, formatRelative } from '#lib/format.ts';

	const STEPS = [
		'Reading your CV',
		'Finding your roles, dates and bullets',
		'Building your profile'
	];

	let phase = $state<'choose' | 'running' | 'review'>('choose');
	let mode = $state('file');
	let file = $state<File | null>(null);
	let text = $state('');
	let model = $state<AiModel | null>(null);
	let error = $state<string | null>(null);
	let controller: AbortController | null = null;

	let uploads = $state<UploadSummary[]>([]);
	let deleting = $state<UploadSummary | null>(null);
	let deleteOpen = $state(false);

	let draft = $state<CvContent | null>(null);
	let sourceName = $state('');
	let usedModel = $state<AiModel | null>(null);
	let profileName = $state('');
	let saving = $state(false);

	/** An import takes an AI run and makes a profile: set when either limit is reached. */
	const blocked = $derived(
		blockedReason(session.usage?.ai_runs, {
			meter: session.usage?.profiles,
			what: 'Importing a CV makes a new profile.'
		})
	);
	const ready = $derived(
		model !== null && blocked === null && (mode === 'file' ? file !== null : text.trim().length > 0)
	);

	function refreshUsage() {
		session.refreshUsage().catch(() => {});
	}

	onMount(async () => {
		try {
			const me = await session.loadMe();
			model = pickModel(me.preferred_ai_model, session.aiModels, session.defaultAiModel);
		} catch {
			model = pickModel(null, session.aiModels, session.defaultAiModel);
		}
		refreshUsage();
		await loadUploads();
	});

	async function loadUploads() {
		try {
			uploads = await unwrap(api.GET('/api/v1/uploads'));
		} catch (failure) {
			toast.error(errorMessage(failure));
		}
	}

	async function start(source: ImportSource, name: string) {
		if (!model) return;
		phase = 'running';
		error = null;
		controller = new AbortController();
		try {
			const result = await runImport(source, model, controller.signal);
			draft = result.draft;
			usedModel = result.ai_model;
			sourceName = name;
			profileName = result.draft.basics.name ? `${result.draft.basics.name}` : 'Imported profile';
			phase = 'review';
			if (result.upload_id) void loadUploads();
		} catch (failure) {
			if (failure instanceof DOMException && failure.name === 'AbortError') {
				phase = 'choose';
				return;
			}
			error = errorMessage(failure);
			phase = 'choose';
			void loadUploads();
		} finally {
			controller = null;
			refreshUsage();
		}
	}

	function submit(event: SubmitEvent) {
		event.preventDefault();
		if (mode === 'file' && file) void start({ file }, file.name);
		else if (mode === 'text' && text.trim()) void start({ text: text.trim() }, 'pasted text');
	}

	async function save() {
		if (!draft) return;
		saving = true;
		try {
			const profile = await unwrap(
				api.POST('/api/v1/profiles', {
					body: { name: profileName.trim() || 'Imported profile', content: draft }
				})
			);
			toast.info('Profile saved.');
			await goto(resolve('/app/profiles/[id]', { id: profile.id }));
		} catch (failure) {
			toast.error(errorMessage(failure));
		} finally {
			saving = false;
		}
	}

	function discard() {
		draft = null;
		phase = 'choose';
	}

	async function removeUpload() {
		if (!deleting) return;
		try {
			await unwrap(
				api.DELETE('/api/v1/uploads/{upload_id}', {
					params: { path: { upload_id: deleting.id } }
				})
			);
			uploads = uploads.filter((upload) => upload.id !== deleting?.id);
			toast.info('File deleted.');
		} catch (failure) {
			toast.error(errorMessage(failure));
		} finally {
			deleteOpen = false;
		}
	}
</script>

<Page title="Import">
	{#snippet actions()}
		{#if phase === 'review'}
			<Button onclick={discard}>Discard</Button>
			<Button variant="primary" loading={saving} onclick={save}>Save profile</Button>
		{/if}
	{/snippet}

	{#if phase === 'choose'}
		<Card title="Import a CV">
			<form class="flex flex-col gap-5" onsubmit={submit}>
				<Tabs
					label="Import from"
					tabs={[
						{ id: 'file', label: 'Upload a file' },
						{ id: 'text', label: 'Paste text' }
					]}
					bind:value={mode}
				>
					{#snippet panel(id)}
						<div class="pt-4">
							{#if id === 'file'}
								<Dropzone bind:file label="CV file" />
							{:else}
								<Textarea
									label="CV text"
									rows={12}
									bind:value={text}
									help="Paste the whole CV. Formatting is not needed."
								/>
							{/if}
						</div>
					{/snippet}
				</Tabs>
				<ModelSelect
					bind:value={model}
					models={session.aiModels}
					plan={session.me?.plan}
					enforced={session.plansEnforced}
					help="Free models cost you nothing extra; Pro models are more capable."
				/>
				{#if error}
					<p class="text-sm text-danger" role="alert">{error}</p>
				{/if}
				{#if blocked}
					<!-- Next to the button it disables, so the reason is where the user looks. -->
					<LimitNotice
						id="import-blocked"
						message={blocked}
						upgrade={canUpgrade(session.usage, session.billingEnabled)}
					/>
				{/if}
				<div>
					<Button
						type="submit"
						variant="primary"
						icon="import"
						disabled={!ready}
						aria-describedby={blocked ? 'import-blocked' : undefined}>Import CV</Button
					>
				</div>
			</form>
		</Card>

		{#if uploads.length > 0}
			<Card title="Earlier uploads" padding="none">
				<ul>
					{#each uploads as upload (upload.id)}
						<li class="flex h-12 items-center gap-3 border-t border-line px-5">
							<div class="min-w-0 flex-1">
								<p class="truncate text-base text-fg">{upload.filename}</p>
							</div>
							<span class="hidden text-sm text-fg-muted sm:inline">
								<span class="font-mono">{formatBytes(upload.size_bytes)}</span>
								· {formatRelative(upload.created_at)}
							</span>
							<Button
								size="sm"
								disabled={!model || blocked !== null}
								onclick={() => start({ uploadId: upload.id }, upload.filename)}
							>
								Import again
							</Button>
							<IconButton
								label="Delete {upload.filename}"
								icon="delete"
								onclick={() => {
									deleting = upload;
									deleteOpen = true;
								}}
							/>
						</li>
					{/each}
				</ul>
			</Card>
		{/if}
	{:else if phase === 'running'}
		<GenerationProgress
			steps={STEPS}
			caption="Importing with {model ? modelLabel(model, session.aiModels) : ''}"
			oncancel={() => controller?.abort()}
		/>
	{:else if draft}
		<div role="status" class="flex items-start gap-3 rounded-lg border border-line bg-surface p-4">
			<span class="mt-0.5 text-fg"><Icon name="placeholder-warning" /></span>
			<div>
				<p class="text-base font-medium text-fg">
					Imported from {sourceName}. Check every entry before using it.
				</p>
				<p class="text-sm text-fg-muted">
					Extracted with {usedModel ? modelLabel(usedModel, session.aiModels) : 'AI'}. Nothing is
					saved until you save the profile.
				</p>
			</div>
		</div>
		<Card title="Profile">
			<Input
				label="Profile name"
				bind:value={profileName}
				help="Only you see this, for example Data engineering or Backend."
			/>
		</Card>
		<CvEditor bind:content={draft} />
	{/if}
</Page>

<ConfirmDialog
	bind:open={deleteOpen}
	title="Delete this file?"
	message="{deleting?.filename ??
		'The file'} will be deleted. Profiles you imported from it stay as they are."
	confirmLabel="Delete file"
	danger
	onconfirm={removeUpload}
/>
