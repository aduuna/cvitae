<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { recentUploads } from '#lib/ai/imports.ts';
	import { modelLabel } from '#lib/ai/models.ts';
	import { api, unwrap } from '#lib/api/client.ts';
	import { session } from '#lib/auth/session.svelte.ts';
	import { canUpgrade } from '#lib/billing/plans.ts';
	import {
		confirmTemplate,
		createTemplateDraft,
		deleteTemplate,
		loadTemplatePreview,
		NAME_MAX,
		pdfUploads,
		templateProblem,
		templatesBlocked,
		type TemplateProblem,
		type TemplateSourceInput
	} from '#lib/custom-templates.ts';
	import GenerationProgress from '#lib/components/ai/GenerationProgress.svelte';
	import LimitNotice from '#lib/components/billing/LimitNotice.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import Dialog from '#lib/components/ui/Dialog.svelte';
	import Dropzone from '#lib/components/ui/Dropzone.svelte';
	import Input from '#lib/components/ui/Input.svelte';
	import type { CustomTemplate, CustomTemplateDraft, UploadSummary } from '#lib/cv/types.ts';
	import { formatBytes, formatRelative } from '#lib/format.ts';
	import { svgDataUrl } from '#lib/preview.svelte.ts';

	interface Props {
		/** The template is saved and usable: `preview` is its first page, to show on its card. */
		onsaved: (template: CustomTemplate, preview: string | null) => void;
		/** The dialog is done, however it ended. The parent unmounts it. */
		onclose: () => void;
	}

	let { onsaved, onclose }: Props = $props();

	const STEPS = [
		"Reading your CV's design",
		'Writing the template',
		'Checking that it draws your CV',
		'Comparing it with your original'
	];

	let open = $state(true);
	let phase = $state<'choose' | 'running' | 'review'>('choose');
	let file = $state<File | null>(null);
	let uploads = $state<UploadSummary[]>([]);
	let problem = $state<TemplateProblem | null>(null);
	let controller: AbortController | null = null;

	let draft = $state<CustomTemplateDraft | null>(null);
	/** The draft's first page; undefined while it renders, null when it could not be. */
	let preview = $state<string | null | undefined>(undefined);
	let name = $state('');
	let saving = $state(false);
	let discarding = $state(false);
	let confirmOpen = $state(false);

	let body: HTMLDivElement | undefined = $state();
	let nameInput: HTMLInputElement | undefined = $state();
	let shownPhase = 'choose';

	// The button that started a phase leaves the page with it, which would drop focus out of the
	// dialog and leave Escape and Tab with nothing to act on. Move it to what the phase is about.
	$effect(() => {
		const current = phase;
		if (current === shownPhase) return;
		shownPhase = current;
		tick().then(() => (current === 'review' ? nameInput : body)?.focus());
	});

	const blocked = $derived(templatesBlocked(session.usage));
	const upgrade = $derived(canUpgrade(session.usage, session.billingEnabled));
	const earlier = $derived(recentUploads(pdfUploads(uploads)));
	const nameProblem = $derived(name.trim() ? undefined : 'Give the template a name.');

	onMount(async () => {
		session.loadUsage().catch(() => {});
		try {
			uploads = await unwrap(api.GET('/api/v1/uploads'));
		} catch {
			// Earlier uploads are a shortcut; a new file still works.
		}
	});

	function refreshUsage() {
		session.refreshUsage().catch(() => {});
	}

	async function start(source: TemplateSourceInput) {
		problem = null;
		phase = 'running';
		const own = new AbortController();
		controller = own;
		try {
			const result = await createTemplateDraft(source, own.signal);
			draft = result;
			name = result.name;
			preview = undefined;
			phase = 'review';
			loadTemplatePreview(result.id).then(
				(page) => (preview = page),
				() => (preview = null)
			);
		} catch (failure) {
			if (failure instanceof DOMException && failure.name === 'AbortError') return;
			problem = templateProblem(failure);
			phase = 'choose';
		} finally {
			if (controller === own) controller = null;
			refreshUsage();
		}
	}

	function cancel() {
		controller?.abort();
		controller = null;
		phase = 'choose';
	}

	async function save() {
		if (!draft || nameProblem) return;
		saving = true;
		problem = null;
		try {
			const saved = await confirmTemplate(draft.id, name.trim());
			onsaved(saved, preview ?? null);
			onclose();
		} catch (failure) {
			problem = templateProblem(failure);
			refreshUsage();
		} finally {
			saving = false;
		}
	}

	/** Deletes the draft: it is not listed anywhere, so it could not be found again. */
	async function discard() {
		if (!draft) return onclose();
		discarding = true;
		try {
			await deleteTemplate(draft.id);
		} catch {
			// An undeleted draft is hidden and replaced by the next one.
		} finally {
			discarding = false;
			confirmOpen = false;
			onclose();
		}
	}

	/** Escape, the close button or a click outside. A draft cost AI usage, so it asks first. */
	function dismiss() {
		if (phase === 'running') {
			controller?.abort();
			onclose();
		} else if (phase === 'review' && draft) {
			open = true;
			confirmOpen = true;
		} else {
			onclose();
		}
	}
</script>

<Dialog
	bind:open
	title="Add your own template"
	size={phase === 'review' ? 'lg' : 'md'}
	onclose={dismiss}
>
	<div bind:this={body} tabindex="-1" class="outline-none">
		{#if phase === 'choose'}
			<div class="flex flex-col gap-4">
				<div class="flex flex-col gap-2 text-base text-fg">
					<p>
						Upload a CV whose design you like. Claude rebuilds how it looks as a template for your
						own CVs: the layout, fonts, colours and spacing. The text of that CV is not copied into
						the template, and only you can use it.
					</p>
					<p class="text-sm text-fg-muted">
						Making a template takes a little of your AI usage and runs on Claude, whichever model
						you chose for other tasks. It can take up to 2 minutes, and nothing is saved until you
						have seen the result.
					</p>
				</div>
				<Dropzone bind:file label="CV file" pdfOnly />
				{#if problem}
					{#if problem.limit}
						<LimitNotice message={problem.message} {upgrade} />
					{:else}
						<p class="text-sm text-danger" role="alert">{problem.message}</p>
					{/if}
				{:else if blocked}
					<LimitNotice message={blocked} {upgrade} />
				{/if}
				{#if earlier.length > 0}
					<section class="flex flex-col gap-2 border-t border-line pt-4" aria-labelledby="earlier">
						<h3 id="earlier" class="text-sm font-medium text-fg">Or use an earlier upload</h3>
						<ul class="rounded-md border border-line">
							{#each earlier as upload (upload.id)}
								<li class="flex h-11 items-center gap-3 border-t border-line px-3 first:border-t-0">
									<p class="min-w-0 flex-1 truncate text-base text-fg">{upload.filename}</p>
									<span class="hidden text-sm text-fg-muted sm:inline">
										{formatBytes(upload.size_bytes)} · {formatRelative(upload.created_at)}
									</span>
									<Button
										size="sm"
										disabled={blocked !== null}
										aria-label="Use {upload.filename}"
										onclick={() => start({ uploadId: upload.id })}
									>
										Use this file
									</Button>
								</li>
							{/each}
						</ul>
					</section>
				{/if}
			</div>
		{:else if phase === 'running'}
			<GenerationProgress
				plain
				steps={STEPS}
				stepSeconds={20}
				caption="Working with Claude"
				oncancel={cancel}
			/>
		{:else if draft}
			<div class="flex flex-col gap-4">
				<p class="text-sm text-fg-muted" role="status">
					Made with {modelLabel(draft.ai_model, session.aiModels)}. The preview shows your default
					profile, or sample data until you have one. Nothing is saved until you save the template.
				</p>
				<div class="flex flex-col gap-5 sm:flex-row">
					<div class="flex shrink-0 justify-center rounded-md bg-canvas p-4 sm:w-80">
						{#if preview}
							<img
								src={svgDataUrl(preview)}
								alt="Preview of the new template"
								class="aspect-[210/297] w-full max-w-64 bg-paper shadow-page"
							/>
						{:else if preview === null}
							<div
								class="flex aspect-[210/297] w-full max-w-64 items-center justify-center bg-surface p-4 text-center text-sm text-fg-muted shadow-page"
							>
								The preview could not be rendered. You can still save the template.
							</div>
						{:else}
							<div
								class="aspect-[210/297] w-full max-w-64 animate-pulse bg-surface shadow-page"
								aria-hidden="true"
							></div>
						{/if}
					</div>
					<div class="flex min-w-0 flex-1 flex-col gap-3">
						<Input
							label="Template name"
							bind:value={name}
							bind:ref={nameInput}
							maxlength={NAME_MAX}
							error={nameProblem}
							help="Only you see this."
						/>
						{#if draft.description}
							<p class="text-sm text-fg-muted">{draft.description}</p>
						{/if}
						{#if problem}
							{#if problem.limit}
								<LimitNotice message={problem.message} {upgrade} />
							{:else}
								<p class="text-sm text-danger" role="alert">{problem.message}</p>
							{/if}
						{/if}
					</div>
				</div>
			</div>
		{/if}
	</div>
	{#snippet footer()}
		{#if phase === 'choose'}
			<Button onclick={dismiss}>Cancel</Button>
			<Button
				variant="primary"
				icon="new"
				disabled={file === null || blocked !== null}
				onclick={() => file && start({ file })}
			>
				Make template
			</Button>
		{:else if phase === 'review'}
			<Button loading={discarding} disabled={saving} onclick={discard}>Discard</Button>
			<Button
				variant="primary"
				loading={saving}
				disabled={discarding || nameProblem !== undefined}
				onclick={save}
			>
				Save template
			</Button>
		{/if}
	{/snippet}
</Dialog>

<ConfirmDialog
	bind:open={confirmOpen}
	title="Discard this template?"
	message="It is not saved yet. If you discard it, making another takes more of your AI usage."
	confirmLabel="Discard template"
	cancelLabel="Keep reviewing"
	danger
	onconfirm={discard}
/>
