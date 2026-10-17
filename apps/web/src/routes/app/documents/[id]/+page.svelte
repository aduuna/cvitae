<script lang="ts">
	import { tick, untrack } from 'svelte';
	import { MediaQuery } from 'svelte/reactivity';
	import { beforeNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { api, errorMessage, unwrap } from '#lib/api/client.ts';
	import { Autosave } from '#lib/autosave.svelte.ts';
	import CvEditor from '#lib/components/cv/CvEditor.svelte';
	import SaveStatus from '#lib/components/cv/SaveStatus.svelte';
	import PlaceholderBanner from '#lib/components/editor/PlaceholderBanner.svelte';
	import PreviewPanel from '#lib/components/editor/PreviewPanel.svelte';
	import VersionsDialog from '#lib/components/editor/VersionsDialog.svelte';
	import { loadSplit, saveSplit } from '#lib/components/editor/split.ts';
	import Page from '#lib/components/shell/Page.svelte';
	import Badge from '#lib/components/ui/Badge.svelte';
	import Button from '#lib/components/ui/Button.svelte';
	import Card from '#lib/components/ui/Card.svelte';
	import IconButton from '#lib/components/ui/IconButton.svelte';
	import Menu from '#lib/components/ui/Menu.svelte';
	import SegmentedControl from '#lib/components/ui/SegmentedControl.svelte';
	import Select from '#lib/components/ui/Select.svelte';
	import Skeleton from '#lib/components/ui/Skeleton.svelte';
	import Splitter from '#lib/components/ui/Splitter.svelte';
	import { toast } from '#lib/components/ui/toasts.svelte.ts';
	import { exportPdf } from '#lib/cv/export.ts';
	import { sourceField } from '#lib/source-links.ts';
	import type { CvContent, CvDocument, PlaceholderRef } from '#lib/cv/types.ts';
	import { formatPages } from '#lib/format.ts';
	import { PreviewState } from '#lib/preview.svelte.ts';
	import { templates } from '#lib/templates.svelte.ts';

	const MIN_EDIT = 360;
	const MIN_PREVIEW = 320;

	const id = $derived(page.params.id ?? '');
	// Under 768px the editor stacks and is read-only (docs/DESIGN.md, Breakpoints).
	const wide = new MediaQuery('min-width: 768px', true);

	let doc = $state<CvDocument | null>(null);
	let loadError = $state<string | null>(null);
	let autosave = $state<Autosave<CvContent> | null>(null);
	let preview = $state<PreviewState | null>(null);

	let versionsOpen = $state(false);
	let exporting = $state(false);
	let placeholders = $state<PlaceholderRef[] | null>(null);
	let narrowView = $state<'form' | 'preview'>('form');

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
		try {
			const loaded = await unwrap(
				api.GET('/api/v1/documents/{document_id}', {
					params: { path: { document_id: documentId } }
				})
			);
			autosave?.dispose();
			preview?.dispose();
			autosave = new Autosave<CvContent>(
				(content) => saveContent(documentId, content),
				loaded.content,
				400
			);
			preview = new PreviewState(documentId);
			doc = loaded;
			void preview.refresh();
		} catch (error) {
			loadError = errorMessage(error);
		}
	}

	async function saveContent(documentId: string, content: CvContent) {
		const updated = await unwrap(
			api.PATCH('/api/v1/documents/{document_id}', {
				params: { path: { document_id: documentId } },
				body: { content }
			})
		);
		if (doc?.id === documentId) doc.updated_at = updated.updated_at;
		void preview?.refresh();
	}

	$effect(() => {
		void load(id);
		templates.load().catch(() => toast.error('Templates could not load. Reload to try again.'));
	});

	$effect(() => {
		if (!doc || !autosave) return;
		const content = $state.snapshot(doc.content);
		const saver = autosave;
		untrack(() => saver.schedule(content));
	});

	$effect(() => () => {
		autosave?.dispose();
		preview?.dispose();
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

	async function changeTemplate(templateId: string) {
		if (!doc || templateId === doc.template_id) return;
		const previous = doc.template_id;
		doc.template_id = templateId;
		try {
			await flush();
			await unwrap(
				api.PATCH('/api/v1/documents/{document_id}', {
					params: { path: { document_id: doc.id } },
					body: { template_id: templateId }
				})
			);
			void preview?.refresh();
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

	function restored(updated: CvDocument) {
		if (!doc) return;
		autosave?.reset(updated.content);
		doc.content = updated.content;
		doc.updated_at = updated.updated_at;
		placeholders = null;
		void preview?.refresh();
	}

	// Briefly rings what a jump landed on, so the eye finds it: the item, section or header the
	// target names, else the field itself (a bullet or the summary).
	const FLASH = ['ring-2', 'ring-accent', 'ring-offset-2', 'ring-offset-surface'];

	/** Opens the form field for a preview link target: an id, "summary" or "basics". */
	async function openField(target: string) {
		narrowView = 'form';
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

<Page title={doc?.name ?? 'CV'} width="full">
	{#snippet actions()}
		{#if doc}
			{#if autosave}<SaveStatus {autosave} />{/if}
			{#if preview?.pageCount}
				<Badge variant="outline">{formatPages(preview.pageCount)}</Badge>
			{/if}
			<div class="w-36">
				<Select
					aria-label="Template"
					value={doc.template_id}
					disabled={!wide.current}
					options={templates.list.length
						? templates.list.map((template) => ({ value: template.id, label: template.name }))
						: [{ value: doc.template_id, label: templates.name(doc.template_id) }]}
					onchange={(event) => changeTemplate(event.currentTarget.value)}
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
			<div
				bind:this={editPanel}
				class="min-h-0 shrink-0 overflow-y-auto"
				style:width="{editWidth}px"
			>
				<div class="flex flex-col gap-4 p-4">
					{#if placeholders}
						<PlaceholderBanner
							{placeholders}
							content={doc.content}
							onfocus={focusPlaceholder}
							ondismiss={() => (placeholders = null)}
						/>
					{/if}
					<CvEditor bind:content={doc.content} />
				</div>
			</div>
			<Splitter
				bind:value={() => editWidth, (value) => (split = value)}
				min={MIN_EDIT}
				max={maxEdit}
				label="Resize edit panel"
				onchange={saveSplit}
			/>
			<div class="min-w-0 flex-1"><PreviewPanel {preview} onpick={openField} /></div>
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
			{#if narrowView === 'form'}
				<div bind:this={editPanel} class="min-h-0 flex-1 overflow-y-auto">
					<div class="flex flex-col gap-4 p-4">
						<p class="rounded-lg border border-line bg-surface p-3 text-sm text-fg-muted">
							Editing needs a wider screen. You can still preview and export this CV.
						</p>
						{#if placeholders}
							<PlaceholderBanner
								{placeholders}
								content={doc.content}
								onfocus={focusPlaceholder}
								ondismiss={() => (placeholders = null)}
							/>
						{/if}
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
