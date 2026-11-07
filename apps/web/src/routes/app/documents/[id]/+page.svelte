<script lang="ts">
	import { tick, untrack } from 'svelte';
	import { MediaQuery } from 'svelte/reactivity';
	import { beforeNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { AiEditChat } from '#lib/ai/edit.svelte.ts';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { Autosave } from '#lib/autosave.svelte.ts';
	import AtsDialog from '#lib/components/ats/AtsDialog.svelte';
	import CvEditor from '#lib/components/cv/CvEditor.svelte';
	import SaveStatus from '#lib/components/cv/SaveStatus.svelte';
	import AiEditPanel from '#lib/components/editor/AiEditPanel.svelte';
	import MarkdownPanel from '#lib/components/editor/MarkdownPanel.svelte';
	import { loadMode, saveMode, type EditMode } from '#lib/components/editor/mode.ts';
	import PlaceholderBanner from '#lib/components/editor/PlaceholderBanner.svelte';
	import PreviewPanel from '#lib/components/editor/PreviewPanel.svelte';
	import TypstPanel from '#lib/components/editor/TypstPanel.svelte';
	import VersionsDialog from '#lib/components/editor/VersionsDialog.svelte';
	import { loadSplit, saveSplit } from '#lib/components/editor/split.ts';
	import Page from '#lib/components/shell/Page.svelte';
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import ConfirmDialog from '#lib/components/ui/ConfirmDialog.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Menu from '#lib/components/ui/Menu.svelte';
	import SegmentedControl from '#lib/components/ui/SegmentedControl.svelte';
	import Select from '#lib/components/ui/Select.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import Splitter from '#lib/components/ui/Splitter.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import { exportPdf } from '#lib/cv/export.ts';
	import { sourceField } from '#lib/source-links.ts';
	import type { CvContent, CvDocument, DocumentAts, PlaceholderRef } from '#lib/cv/types.ts';
	import { formatPages } from '#lib/format.ts';
	import { PreviewState } from '#lib/preview.svelte.ts';
	import { templates } from '#lib/templates.svelte.ts';

	const MIN_EDIT = 360;
	const MIN_PREVIEW = 320;

	/** What autosave keeps on the server: the content and the custom layout. */
	interface Draft {
		content: CvContent;
		layout: string | null;
	}

	const id = $derived(page.params.id ?? '');
	// Under 768px the editor stacks and is read-only (docs/DESIGN.md, Breakpoints).
	const wide = new MediaQuery('min-width: 768px', true);

	let doc = $state<CvDocument | null>(null);
	let loadError = $state<string | null>(null);
	let autosave = $state<Autosave<Draft> | null>(null);
	let preview = $state<PreviewState | null>(null);
	let chat = $state<AiEditChat | null>(null);

	let versionsOpen = $state(false);
	let atsOpen = $state(false);
	let ats = $state<DocumentAts | null>(null);
	let exporting = $state(false);
	let placeholders = $state<PlaceholderRef[] | null>(null);
	let narrowView = $state<'form' | 'preview'>('form');

	let mode = $state<EditMode>(loadMode());
	let markdownInvalid = $state(false);
	// Bumped when the content changes from outside the editor, so the Markdown text is rewritten.
	let revision = $state(0);
	let pendingMode = $state<EditMode | null>(null);
	// The preview part that asked to leave Markdown, to open once the form is showing.
	let pendingTarget = $state<string | null>(null);
	let discardOpen = $state(false);
	let pendingTemplate = $state<string | null>(null);
	let switchOpen = $state(false);
	let resetOpen = $state(false);

	let containerWidth = $state(0);
	let split = $state<number | null>(loadSplit());
	let editPanel: HTMLDivElement | undefined = $state();

	const maxEdit = $derived(Math.max(MIN_EDIT, containerWidth - MIN_PREVIEW));
	const editWidth = $derived(
		Math.min(maxEdit, Math.max(MIN_EDIT, split ?? Math.round(containerWidth * 0.45)))
	);

	async function load(documentId: string) {
		doc = null;
		loadError = null;
		placeholders = null;
		ats = null;
		markdownInvalid = false;
		try {
			const loaded = await unwrap(
				api.GET('/api/v1/documents/{document_id}', {
					params: { path: { document_id: documentId } }
				})
			);
			autosave?.dispose();
			preview?.dispose();
			chat?.dispose();
			autosave = new Autosave<Draft>(
				(draft) => saveDraft(documentId, draft),
				{ content: loaded.content, layout: loaded.layout },
				400
			);
			preview = new PreviewState(documentId);
			chat = new AiEditChat(documentId, {
				content: () => doc?.content ?? loaded.content,
				save: flush,
				apply: applyEdit
			});
			doc = loaded;
			void preview.refresh();
			void refreshAts();
		} catch (error) {
			loadError = errorMessage(error);
		}
	}

	async function saveDraft(documentId: string, draft: Draft) {
		const updated = await unwrap(
			api.PATCH('/api/v1/documents/{document_id}', {
				params: { path: { document_id: documentId } },
				body: { content: draft.content, layout: draft.layout }
			})
		);
		if (doc?.id === documentId) doc.updated_at = updated.updated_at;
		void preview?.refresh();
		void refreshAts();
	}

	/** The saved CV's ATS score: no AI, so it follows every save. */
	async function refreshAts() {
		const current = doc;
		if (!current) return;
		try {
			const result = await unwrap(
				api.GET('/api/v1/documents/{document_id}/ats', {
					params: { path: { document_id: current.id } }
				})
			);
			if (doc?.id === current.id) {
				ats = result;
				doc.job_id = result.job?.id ?? null;
			}
		} catch {
			// The button keeps the last score; the next save tries again.
		}
	}

	// The preview records the page count the length check reads, so check again when it changes.
	$effect(() => {
		if (preview?.pageCount != null) untrack(() => void refreshAts());
	});

	$effect(() => {
		void load(id);
		templates.load().catch(() => toast.error('Templates could not load. Reload to try again.'));
	});

	$effect(() => {
		if (!doc || !autosave) return;
		const draft = { content: $state.snapshot(doc.content), layout: doc.layout };
		const saver = autosave;
		untrack(() => saver.schedule(draft));
	});

	$effect(() => () => {
		autosave?.dispose();
		preview?.dispose();
		chat?.dispose();
	});

	beforeNavigate(() => {
		if (autosave?.dirty) void autosave.flush();
	});

	function onbeforeunload(event: BeforeUnloadEvent) {
		if (autosave?.dirty) event.preventDefault();
	}

	async function flush() {
		await autosave?.flush();
	}

	/** Switch mode now, or after asking when the Markdown has lines that cannot be saved. */
	function requestMode(next: EditMode, target: string | null = null) {
		if (next === mode) return;
		if (mode === 'markdown' && markdownInvalid) {
			pendingMode = next;
			pendingTarget = target;
			discardOpen = true;
			return;
		}
		setMode(next);
	}

	function setMode(next: EditMode) {
		mode = next;
		markdownInvalid = false;
		saveMode(next);
	}

	function selectTemplate(select: HTMLSelectElement) {
		if (!doc || select.value === doc.template_id) return;
		if (doc.layout === null) {
			void changeTemplate(select.value);
			return;
		}
		// A custom layout is replaced by the switch: ask first, showing the current template meanwhile.
		pendingTemplate = select.value;
		select.value = doc.template_id;
		switchOpen = true;
	}

	async function changeTemplate(templateId: string) {
		if (!doc || templateId === doc.template_id) return;
		const previous = doc.template_id;
		doc.template_id = templateId;
		try {
			await flush();
			const updated = await unwrap(
				api.PATCH('/api/v1/documents/{document_id}', {
					params: { path: { document_id: doc.id } },
					body: { template_id: templateId }
				})
			);
			// The server drops a custom layout on a switch.
			autosave?.reset({ content: $state.snapshot(doc.content), layout: updated.layout });
			doc.layout = updated.layout;
			void preview?.refresh();
			void refreshAts();
		} catch (error) {
			doc.template_id = previous;
			toast.error(errorMessage(error));
		}
	}

	async function runExport(force = false) {
		if (!doc) return;
		exporting = true;
		try {
			await flush();
			const result = await exportPdf(doc.id, force);
			placeholders = result.ok ? null : result.placeholders;
		} catch (error) {
			toast.error(errorMessage(error));
		} finally {
			exporting = false;
		}
	}

	/** An AI edit goes into the form as typing would, and autosave saves it. */
	function applyEdit(content: CvContent) {
		if (!doc) return;
		doc.content = content;
		placeholders = null;
		// The Markdown text, if it is showing, is written again from the new content.
		revision++;
	}

	function restored(updated: CvDocument) {
		if (!doc) return;
		autosave?.reset({ content: updated.content, layout: updated.layout });
		doc.content = updated.content;
		doc.layout = updated.layout;
		doc.updated_at = updated.updated_at;
		placeholders = null;
		markdownInvalid = false;
		revision++;
		void preview?.refresh();
		void refreshAts();
	}

	// Briefly rings what a jump landed on, so the eye finds it: the item, section or header the
	// target names, else the field itself (a bullet or the summary).
	const FLASH = ['ring-2', 'ring-accent', 'ring-offset-2', 'ring-offset-surface'];

	/** Opens the form field for a preview link target: an id, "summary" or "basics". From
	 * Markdown or Typst mode it switches to Form first. */
	async function openField(target: string) {
		narrowView = 'form';
		if (wide.current) requestMode('form', target);
		if (mode !== 'form' && wide.current) return;
		await tick();
		const field = editPanel ? sourceField(editPanel, target) : null;
		if (!editPanel || !field) return;
		field.scrollIntoView({ block: 'center' });
		field.focus({ preventScroll: true });
		const ring =
			editPanel.querySelector<HTMLElement>(`[data-cv-id="${CSS.escape(target)}"]`) ?? field;
		ring.classList.add(...FLASH);
		setTimeout(() => ring.classList.remove(...FLASH), 1200);
	}

	function focusPlaceholder(ref: PlaceholderRef) {
		void openField(ref.bullet_id ?? 'summary');
	}
</script>

<svelte:window {onbeforeunload} />

<!-- Why export stopped: beside the preview, where the placeholders show highlighted. -->
{#snippet placeholderNotice()}
	{#if doc && placeholders}
		<PlaceholderBanner
			{placeholders}
			content={doc.content}
			onfocus={focusPlaceholder}
			ondismiss={() => (placeholders = null)}
		/>
	{/if}
{/snippet}

<Page title={doc?.name ?? 'CV'} width="full">
	{#snippet actions()}
		{#if doc}
			{#if autosave}<SaveStatus {autosave} />{/if}
			{#if preview?.pageCount}
				<!-- Under 1024px the preview header's page count is enough, and the title needs the room. -->
				<span class="max-lg:hidden">
					<Badge variant="outline">{formatPages(preview.pageCount)}</Badge>
				</span>
			{/if}
			{#if doc.layout !== null}
				<span class="max-lg:hidden"><Badge variant="outline">Custom layout</Badge></span>
			{/if}
			{@const score = ats?.report?.score ?? null}
			<Button
				variant="secondary"
				icon="ats"
				aria-label={score !== null ? `ATS score ${score} of 100` : 'ATS score'}
				onclick={() => (atsOpen = true)}
			>
				{#if score !== null}
					<span class="max-lg:hidden">ATS</span>
					<span class="tabular-nums">{score}</span>
				{:else}
					ATS<span class="max-lg:hidden">&nbsp;score</span>
				{/if}
			</Button>
			<div class="w-36">
				<Select
					aria-label="Template"
					value={doc.template_id}
					disabled={!wide.current}
					options={templates.list.length
						? templates.list.map((template) => ({ value: template.id, label: template.name }))
						: [{ value: doc.template_id, label: templates.name(doc.template_id) }]}
					onchange={(event) => selectTemplate(event.currentTarget)}
				/>
			</div>
			<IconButton
				label="Version history"
				icon="versions"
				variant="secondary"
				onclick={() => (versionsOpen = true)}
			/>
			<Button variant="primary" icon="download" loading={exporting} onclick={() => runExport()}>
				Export PDF
			</Button>
			<Menu
				label="More export options"
				items={[{ label: 'Export anyway', icon: 'download', onselect: () => runExport(true) }]}
			/>
		{/if}
	{/snippet}

	{#if loadError}
		<div class="mx-auto w-full max-w-240 p-6">
			<Card>
				<p role="alert" class="text-base text-danger">{loadError}</p>
				<div class="mt-3"><Button onclick={() => load(id)}>Try again</Button></div>
			</Card>
		</div>
	{:else if !doc || !preview}
		<div class="mx-auto w-full max-w-240 p-6"><Card><Skeleton lines={6} /></Card></div>
	{:else if wide.current}
		<div class="flex h-full min-h-0" bind:clientWidth={containerWidth}>
			<div class="flex min-h-0 shrink-0 flex-col" style:width="{editWidth}px">
				<div class="flex h-12 shrink-0 items-center border-b border-line bg-surface px-4">
					<SegmentedControl
						label="Editing mode"
						bind:value={() => mode, (next) => requestMode(next)}
						options={[
							{ value: 'form', label: 'Form' },
							{ value: 'markdown', label: 'Markdown' },
							{ value: 'typst', label: 'Typst' }
						]}
					/>
				</div>
				{#if mode === 'form'}
					<div bind:this={editPanel} class="min-h-0 flex-1 overflow-y-auto">
						<div class="p-4"><CvEditor bind:content={doc.content} /></div>
					</div>
					{#if chat}
						<AiEditPanel {chat} content={doc.content} />
					{/if}
				{:else if mode === 'markdown'}
					<div class="min-h-0 flex-1">
						{#key revision}
							<MarkdownPanel
								bind:content={doc.content}
								onvalidity={(valid) => (markdownInvalid = !valid)}
							/>
						{/key}
					</div>
				{:else}
					<div class="min-h-0 flex-1">
						<TypstPanel
							documentId={doc.id}
							templateId={doc.template_id}
							bind:layout={doc.layout}
							diagnostics={preview.diagnostics}
							savedAt={doc.updated_at}
							onreset={() => (resetOpen = true)}
						/>
					</div>
				{/if}
			</div>
			<Splitter
				bind:value={() => editWidth, (value) => (split = value)}
				min={MIN_EDIT}
				max={maxEdit}
				label="Resize edit panel"
				onchange={saveSplit}
			/>
			<div class="min-w-0 flex-1">
				<PreviewPanel
					{preview}
					onpick={openField}
					notice={placeholders ? placeholderNotice : undefined}
				/>
			</div>
		</div>
	{:else}
		<div class="flex h-full min-h-0 flex-col">
			<div class="flex shrink-0 items-center justify-center border-b border-line bg-surface p-2">
				<SegmentedControl
					label="View"
					bind:value={narrowView}
					options={[
						{ value: 'form', label: 'Form' },
						{ value: 'preview', label: 'Preview' }
					]}
				/>
			</div>
			{#if placeholders}
				<div class="shrink-0 px-4 pt-4">{@render placeholderNotice()}</div>
			{/if}
			{#if narrowView === 'form'}
				<div bind:this={editPanel} class="min-h-0 flex-1 overflow-y-auto">
					<div class="flex flex-col gap-4 p-4">
						<p class="rounded-lg border border-line bg-surface p-3 text-sm text-fg-muted">
							Editing needs a wider screen. You can still preview and export this CV.
						</p>
						<CvEditor bind:content={doc.content} disabled />
					</div>
				</div>
			{:else}
				<div class="min-h-0 flex-1"><PreviewPanel {preview} onpick={openField} /></div>
			{/if}
		</div>
	{/if}
</Page>

<VersionsDialog
	bind:open={versionsOpen}
	documentId={id}
	beforeChange={flush}
	onrestored={restored}
/>

<AtsDialog bind:open={atsOpen} documentId={id} {ats} onchange={refreshAts} />

<ConfirmDialog
	bind:open={discardOpen}
	title="Leave Markdown?"
	message="Some lines have errors, so your latest Markdown changes are not saved. Leaving discards them; the CV keeps its last valid content."
	confirmLabel="Discard changes"
	cancelLabel="Keep editing"
	danger
	onconfirm={() => {
		const target = pendingTarget;
		if (pendingMode) setMode(pendingMode);
		pendingMode = null;
		pendingTarget = null;
		// After the dialog has closed and given focus back to where it came from.
		if (target) setTimeout(() => void openField(target), 0);
	}}
	oncancel={() => {
		pendingMode = null;
		pendingTarget = null;
	}}
/>

<ConfirmDialog
	bind:open={switchOpen}
	title="Switch template?"
	message="Switching to {templates.name(
		pendingTemplate ?? ''
	)} replaces your custom layout. Save a version first if you want to keep it."
	confirmLabel="Switch template"
	danger
	onconfirm={async () => {
		if (pendingTemplate) await changeTemplate(pendingTemplate);
		pendingTemplate = null;
	}}
	oncancel={() => (pendingTemplate = null)}
/>

<ConfirmDialog
	bind:open={resetOpen}
	title="Reset layout?"
	message="This CV goes back to the {templates.name(
		doc?.template_id ?? ''
	)} layout. Save a version first if you want to keep your Typst changes."
	confirmLabel="Reset to template"
	danger
	onconfirm={() => {
		if (doc) doc.layout = null;
	}}
/>
